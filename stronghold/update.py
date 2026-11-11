"""Public GitHub release feed, streamed verification and bounded ZIP staging."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from threading import Event
import urllib.request
from urllib.parse import urlsplit
import uuid
import zipfile

REPOSITORY = "https://github.com/Fuppppping/stronghold-assistant"
FEED = REPOSITORY + "/releases/latest/download/update.json"
MAX_ARCHIVE = 512 * 1024**2
MAX_CONTENT = 768 * 1024**2
ROOT_FILES = {"StrongholdAssistant.exe", "README.md", "THIRD_PARTY_NOTICES.md",
              "DEPENDENCIES.json", "LICENSE", "CHANGELOG.md", "PERFORMANCE.md",
              "攻略JSON格式.md", "guide.example.json", "guide.schema.json",
              "使用说明.txt", "SOURCE_PROVENANCE.json"}
DOC_FILES = {"docs/screenshots/" + name for name in
             ("01-live-help.png", "02-ban-evidence.png", "03-lineup-guide.png", "04-compact-overlay.png")}


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d{1,5}\.\d{1,5}\.\d{1,5}", value):
        raise ValueError("更新版本号无效")
    return tuple(map(int, value.lstrip("v").split(".")))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def asset_url(url, version):
    expected = REPOSITORY + f"/releases/download/v{version}/StrongholdAssistant-v{version}-windows-x64.zip"
    if url != expected:
        raise ValueError("更新地址不属于本项目的正式发布包")
    return url


def transport_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.hostname not in {"github.com", "release-assets.githubusercontent.com",
                                       "objects.githubusercontent.com", "github-releases.githubusercontent.com"}):
        raise ValueError("更新连接被重定向到不受信任的地址")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        transport_url(url)
        return super().redirect_request(request, fp, code, message, headers, url)


def open_url(url):
    transport_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "StrongholdAssistant-Updater",
                                                  "Accept": "application/octet-stream"})
    return urllib.request.build_opener(SafeRedirect()).open(request, timeout=25)


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    size: int
    notes: str = ""

    @property
    def page(self):
        return REPOSITORY + "/releases/tag/v" + self.version

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict) or data.get("schema") != 1:
            raise ValueError("无法识别更新清单")
        version = data.get("version")
        version_tuple(version)
        if version.startswith("v"):
            raise ValueError("更新清单版本号不应包含 v")
        url = asset_url(data.get("url"), version)
        sha = data.get("sha256", "")
        if not isinstance(sha, str) or not re.fullmatch("[a-f0-9]{64}", sha):
            raise ValueError("缺少更新包校验码")
        size = data.get("size")
        if type(size) is not int or not 0 < size <= MAX_ARCHIVE:
            raise ValueError("更新包大小无效")
        notes = data.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 16000:
            raise ValueError("更新说明过长")
        return cls(version, url, sha, size, notes)


def check_release():
    with open_url(FEED) as response:
        content = response.read(65537)
    if len(content) > 65536:
        raise ValueError("更新清单过大")
    return Release.parse(json.loads(content))


def safe_member(name):
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError("更新包包含非法路径")
    parts = name.rstrip("/").split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or any(ord(c) < 32 or c in '<>"|?*' for c in part)
                or part.split(".")[0].upper() in reserved):
            raise ValueError("更新包包含不安全的文件名")
    if not (len(parts) == 1 and parts[0] in ROOT_FILES or parts[0] == "licenses" and len(parts) > 1
            or name in DOC_FILES):
        raise ValueError("更新包包含非程序管理的文件")
    return PurePosixPath(*parts)


def extract_payload(archive, task, release):
    payload = task / "payload"
    payload.mkdir()
    hashes, seen, total = {}, set(), 0
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.infolist()) > 4096:
            raise ValueError("更新包文件数过多")
        for member in bundle.infolist():
            if member.is_dir():
                continue
            relative = safe_member(member.filename)
            folded = str(relative).casefold()
            mode = member.external_attr >> 16
            if folded in seen or stat.S_ISLNK(mode):
                raise ValueError("更新包含重复路径或符号链接")
            seen.add(folded)
            total += member.file_size
            if total > MAX_CONTENT or member.file_size > MAX_ARCHIVE:
                raise ValueError("更新包解压后过大")
            path = payload.joinpath(*relative.parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, path.open("xb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            hashes[relative.as_posix()] = digest(path)
    exe = payload / "StrongholdAssistant.exe"
    with exe.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("程序文件格式错误")
    provenance = json.loads((payload / "SOURCE_PROVENANCE.json").read_text(encoding="utf-8"))
    if (provenance.get("version") != release.version or provenance.get("source_repository") != REPOSITORY
            or provenance.get("executable_sha256") != hashes.get("StrongholdAssistant.exe")):
        raise ValueError("程序来源或校验码不匹配")
    return hashes


def download_release(release, cache, progress=lambda done, total: None, cancel=None):
    cancel = cancel or Event()
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    # Room for ZIP, extracted payload, helper and backup; never consume the last few MB.
    if shutil.disk_usage(cache).free < release.size * 4 + 100 * 1024**2:
        raise OSError("更新磁盘空间不足，请预留至少 1 GB")
    task = cache / uuid.uuid4().hex
    task.mkdir()
    archive = task / "download.part"
    try:
        with open_url(release.url) as response, archive.open("xb") as output:
            received, sha = 0, hashlib.sha256()
            while chunk := response.read(1024 * 1024):
                if cancel.is_set():
                    raise InterruptedError("已取消下载")
                received += len(chunk)
                if received > release.size:
                    raise ValueError("下载内容超过清单大小")
                output.write(chunk)
                sha.update(chunk)
                progress(received, release.size)
        if received != release.size or sha.hexdigest() != release.sha256:
            raise ValueError("更新包校验失败，请重新下载")
        if cancel.is_set():
            raise InterruptedError("已取消下载")
        archive.rename(task / "download.zip")
        hashes = extract_payload(task / "download.zip", task, release)
        atomic_json(task / "staged.json", {"version": release.version, "files": hashes})
        return task
    except Exception:
        # This directory was freshly created below the resolved private cache.
        if task.parent == cache and task.name == task.resolve().name:
            shutil.rmtree(task)
        raise
