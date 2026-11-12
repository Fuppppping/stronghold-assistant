from dataclasses import asdict
import hashlib
import io
import json
import os
import ssl
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import zipfile

from stronghold import VERSION
from stronghold import update as up, update_install as install


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {"STRONGHOLD_STATE": str(self.root)})
        self.env.start()
        self.task = self.root / "updates" / uuid.uuid4().hex
        self.task.mkdir(parents=True)
        self.exe = b"MZnew executable"
        self.version = "99.0.0"

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def archive(self, extra=None):
        data = io.BytesIO()
        provenance = {"version": self.version, "source_repository": up.REPOSITORY,
                      "executable_sha256": hashlib.sha256(self.exe).hexdigest()}
        with zipfile.ZipFile(data, "w") as bundle:
            bundle.writestr("StrongholdAssistant.exe", self.exe)
            bundle.writestr("SOURCE_PROVENANCE.json", json.dumps(provenance))
            bundle.writestr("README.md", "new readme")
            if extra:
                for name, content in extra:
                    bundle.writestr(name, content)
        content = data.getvalue()
        release = up.Release(self.version,
            up.REPOSITORY + f"/releases/download/v{self.version}/StrongholdAssistant-v{self.version}-windows-x64.zip",
            hashlib.sha256(content).hexdigest(), len(content), "Release notes")
        return content, release

    def stage(self):
        content, release = self.archive()
        archive = self.task / "download.zip"
        archive.write_bytes(content)
        files = up.extract_payload(archive, self.task, release)
        target = self.root / "installed" / "MyAssistant.exe"
        target.parent.mkdir()
        target.write_bytes(b"MZold executable")
        (target.parent / "README.md").write_text("old readme")
        plan = {"schema": 1, "version": self.version, "files": files, "target": str(target),
                "pid": 999, "nonce": uuid.uuid4().hex, "old_sha256": up.digest(target)}
        return plan, target

    def test_semantic_version_order(self):
        self.assertGreater(up.version_tuple("0.3.10"), up.version_tuple("v0.3.9"))
        self.assertGreater(up.version_tuple("1.0.0"), up.version_tuple(VERSION))
        for value in (None, 3, "0.3.4-beta", "1.2", "1.2.3/evil", "999999.0.0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                up.version_tuple(value)

    def test_feed_restricts_repo_and_digest(self):
        _, release = self.archive()
        raw = dict(schema=1, **asdict(release))
        self.assertEqual(up.Release.parse(raw), release)
        for key, value in [("url", "https://evil.invalid/file.zip"), ("url", release.url + "?x=1"),
                           ("size", -1), ("size", True), ("sha256", "abc"), ("notes", "x" * 16001)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                up.Release.parse(raw | {key: value})

    def test_reject_unsafe_redirects(self):
        for url in ("http://github.com/a", "https://github.com.evil/a", "https://github.com:123/a",
                    "https://user@github.com/a", "file:///C:/app.exe"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                up.transport_url(url)

    def test_https_supplements_system_and_empty_stores_with_verified_roots(self):
        for context in (ssl.create_default_context(), ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)):
            original = set(context.get_ca_certs(binary_form=True))
            with self.subTest(system_roots=len(original)), \
                    patch.object(up.ssl, "create_default_context", return_value=context), \
                    patch.object(up.urllib.request, "build_opener") as build:
                up.open_url(up.FEED)
                roots = set(context.get_ca_certs(binary_form=True))
                self.assertTrue(roots)
                self.assertTrue(original <= roots)
                self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(context.check_hostname)
                handlers = build.call_args.args
                self.assertTrue(any(isinstance(h, up.SafeRedirect) for h in handlers))
                https = next(h for h in handlers if isinstance(h, up.urllib.request.HTTPSHandler))
                self.assertIs(https._context, context)
                request = build.return_value.open.call_args.args[0]
                self.assertEqual(request.full_url, up.FEED)

    def test_missing_ca_bundle_fails_without_opening_an_unverified_connection(self):
        with patch.object(up.certifi, "where", return_value=str(self.root / "missing.pem")), \
                patch.object(up.urllib.request, "build_opener") as build:
            with self.assertRaises(OSError):
                up.open_url(up.FEED)
            build.assert_not_called()

    def test_reject_traversal_ads_and_windows_aliases(self):
        for name in ("../oops.exe", "/README.md", "licenses/../README.md", "licenses\\a",
                     "licenses/C:/x", "licenses/NUL.txt", "licenses/a.", "licenses/a ",
                     "licenses//a", "settings.json", "guides/own.json", "licenses/a:payload"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                up.safe_member(name)

    def test_successful_download_and_stage(self):
        content, release = self.archive()
        progress = []
        with patch.object(up, "open_url", return_value=io.BytesIO(content)):
            task = up.download_release(release, self.root / "updates", lambda a, b: progress.append((a, b)))
        self.assertEqual((task / "payload/StrongholdAssistant.exe").read_bytes(), self.exe)
        self.assertEqual(progress[-1], (len(content), len(content)))
        self.assertTrue((task / "staged.json").is_file())

    def test_corrupt_or_truncated_download_removes_only_own_task(self):
        content, release = self.archive()
        for damaged in (content[:-4], content[:-1] + b"X", content + b"X"):
            with patch.object(up, "open_url", return_value=io.BytesIO(damaged)), self.assertRaises(ValueError):
                up.download_release(release, self.root / "updates")
        self.assertEqual(list((self.root / "updates").iterdir()), [self.task])

    def test_cancel_download(self):
        content, release = self.archive()
        cancel = Event()
        cancel.set()
        with patch.object(up, "open_url", return_value=io.BytesIO(content)), self.assertRaises(InterruptedError):
            up.download_release(release, self.root / "updates", cancel=cancel)

    def test_zip_rejects_case_duplicate(self):
        content, release = self.archive([("licenses/X.txt", "a"), ("licenses/x.txt", "b")])
        archive = self.task / "bad.zip"
        archive.write_bytes(content)
        with self.assertRaises(ValueError):
            up.extract_payload(archive, self.task, release)

    def test_zip_rejects_excessive_uncompressed_content(self):
        content, release = self.archive()
        archive = self.task / "bad.zip"
        archive.write_bytes(content)
        with patch.object(up, "MAX_CONTENT", 4), self.assertRaises(ValueError):
            up.extract_payload(archive, self.task, release)

    def test_provenance_mismatch(self):
        content, release = self.archive()
        archive = self.task / "bad.zip"
        archive.write_bytes(content)
        with self.assertRaises(ValueError):
            up.extract_payload(archive, self.task, up.Release("1.0.0", release.url, release.sha256, release.size))

    def test_modified_payload_rejected_before_backup(self):
        plan, target = self.stage()
        (self.task / "payload/README.md").write_text("tampered")
        with self.assertRaises(ValueError):
            install.install_files(self.task, plan)
        self.assertEqual(target.read_bytes(), b"MZold executable")
        self.assertFalse((self.task / "backup").exists())

    def test_transaction_preserves_custom_files_and_rolls_back(self):
        plan, target = self.stage()
        own = target.parent / "my-guide.json"
        own.write_text("private settings")
        changed = install.install_files(self.task, plan)
        self.assertEqual(target.read_bytes(), self.exe)
        self.assertEqual(own.read_text(), "private settings")
        install.rollback(self.task, plan, changed)
        self.assertEqual(target.read_bytes(), b"MZold executable")
        self.assertEqual((target.parent / "README.md").read_text(), "old readme")
        self.assertFalse((target.parent / "SOURCE_PROVENANCE.json").exists())
        self.assertEqual(own.read_text(), "private settings")

    def test_mid_install_failure_restores_completed_files(self):
        plan, target = self.stage()
        original = install.replace_file
        def replace(source, destination):
            if source == self.task / "payload/StrongholdAssistant.exe":
                raise PermissionError("file locked")
            original(source, destination)
        with patch.object(install, "replace_file", side_effect=replace), self.assertRaises(PermissionError):
            install.install_files(self.task, plan)
        self.assertEqual(target.read_bytes(), b"MZold executable")
        self.assertEqual((target.parent / "README.md").read_text(), "old readme")
        self.assertFalse((target.parent / "SOURCE_PROVENANCE.json").exists())

    def test_task_scope_rejects_arbitrary_directory(self):
        for path in (self.root, self.root / "updates" / "not-a-task", self.root / uuid.uuid4().hex):
            with self.assertRaises(ValueError):
                install.task_path(path)
        self.assertEqual(install.task_path(self.task), self.task)

    def helper(self, success=True, commit=True):
        plan, target = self.stage()
        helper = self.task / "update-helper.exe"
        helper.write_bytes(target.read_bytes())
        up.atomic_json(self.task / "plan.json", plan)
        if commit:
            up.atomic_json(self.task / "commit.json", {"nonce": plan["nonce"]})
        calls = []
        def start(args):
            calls.append(args)
            if "--update-health" in args and success:
                up.atomic_json(self.task / "healthy.json", {"nonce": plan["nonce"]})
            return SimpleNamespace(poll=lambda: 1)
        kernel = SimpleNamespace(WaitForSingleObject=lambda handle, timeout: 0, CloseHandle=lambda handle: None)
        with patch.object(install.sys, "executable", str(helper)), \
                patch.object(install, "process_handle", return_value=(kernel, 123)), \
                patch.object(install, "start_process", side_effect=start):
            code = install.helper_main(self.task / "plan.json")
        status = json.loads((self.task / "status.json").read_text())
        return code, target, calls, status

    def test_helper_commits_only_after_healthy_start(self):
        code, target, calls, status = self.helper()
        self.assertEqual(code, 0)
        self.assertEqual(target.read_bytes(), self.exe)
        self.assertEqual(status["state"], "complete")
        self.assertEqual(len(calls), 1)

    def test_helper_failed_new_start_rolls_back_and_restarts_old(self):
        code, target, calls, status = self.helper(success=False)
        self.assertEqual(code, 1)
        self.assertEqual(target.read_bytes(), b"MZold executable")
        self.assertIn("--update-result", calls[-1])
        self.assertEqual(status["state"], "error")

    def test_helper_cannot_install_after_gui_cancelled(self):
        code, target, calls, status = self.helper(commit=False)
        self.assertEqual(code, 1)
        self.assertEqual(target.read_bytes(), b"MZold executable")
        self.assertEqual(calls, [])
        self.assertEqual(status["state"], "cancelled")

    def test_source_does_not_replace_python(self):
        with self.assertRaises(RuntimeError):
            install.prepare_install(self.task)

    def test_win32_process_identity_uses_real_process(self):
        import sys
        kernel, handle = install.process_handle(os.getpid(), Path(sys._base_executable).resolve())
        kernel.CloseHandle(handle)
        with self.assertRaises(ValueError):
            install.process_handle(os.getpid(), self.root / "wrong.exe")


if __name__ == "__main__":
    unittest.main()
