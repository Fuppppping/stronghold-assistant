"""Isolated updater helper. No capture/OCR imports and no elevation requests."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from .update import atomic_json, digest, safe_member, version_tuple


def state_dir():
    return Path(os.environ.get("STRONGHOLD_STATE") or
                Path(os.environ.get("LOCALAPPDATA", ".")) / "StrongholdAssistant").resolve()


def task_path(path):
    path = Path(path).absolute()
    cache = state_dir() / "updates"
    if (path.parent != cache or not re.fullmatch("[a-f0-9]{32}", path.name)
            or path.resolve() != path or cache.resolve() != cache):
        raise ValueError("更新任务不在助手的更新目录内")
    return path


def start_process(args):
    return subprocess.Popen(args, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW)


def prepare_install(task, target=None):
    if not getattr(sys, "frozen", False) and target is None:
        raise RuntimeError("源码运行请从发布页下载程序；源码环境不执行自替换")
    task = task_path(task)
    target = Path(target or sys.executable).resolve()
    if not target.is_file() or target.suffix.casefold() != ".exe":
        raise ValueError("当前程序路径无效")
    # Test write permission before asking the running application to exit.
    probe = target.parent / (".stronghold-write-" + uuid.uuid4().hex)
    try:
        probe.write_bytes(b"")
    finally:
        probe.unlink(missing_ok=True)
    staged = json.loads((task / "staged.json").read_text(encoding="utf-8"))
    for name in ("status.json", "healthy.json", "commit.json"):
        (task / name).unlink(missing_ok=True)
    helper = task / "update-helper.exe"
    shutil.copy2(target, helper)
    plan = {"schema": 1, "pid": os.getpid(), "target": str(target), "old_sha256": digest(target),
            "version": staged["version"], "files": staged["files"], "nonce": uuid.uuid4().hex}
    atomic_json(task / "plan.json", plan)
    return plan


def verify_payload(task, plan):
    version_tuple(plan["version"])
    files = plan["files"]
    if not isinstance(files, dict) or not 2 <= len(files) <= 4096 or "StrongholdAssistant.exe" not in files:
        raise ValueError("待安装文件清单无效")
    for name, sha in files.items():
        rel = safe_member(name)
        source = task / "payload" / rel
        if source.resolve() != source or not source.is_file() or digest(source) != sha:
            raise ValueError("待安装文件被修改：" + name)


def process_handle(pid, expected):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        raise OSError("无法确认原程序进程；助手将保持运行")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(buffer.value).resolve() != expected:
            raise ValueError("原进程与待更新程序不匹配")
    except Exception:
        kernel.CloseHandle(handle)
        raise
    return kernel, handle


def replace_file(source, target, timeout=30):
    temp = target.with_name(".stronghold-" + uuid.uuid4().hex + ".tmp")
    try:
        shutil.copy2(source, temp)
        end = time.monotonic() + timeout
        while True:
            try:
                os.replace(temp, target)
                break
            except PermissionError:
                if time.monotonic() >= end:
                    raise
                time.sleep(.25)
    finally:
        temp.unlink(missing_ok=True)


def destinations(task, plan):
    target = Path(plan["target"])
    result = []
    # Replace the executable last; doc/notice files are managed alongside it.
    for name in sorted(plan["files"], key=lambda name: name == "StrongholdAssistant.exe"):
        safe_member(name)
        destination = target if name == "StrongholdAssistant.exe" else target.parent / name
        if destination.resolve() != destination:
            raise ValueError("安装目录包含链接或路径重定向")
        result.append((name, destination))
    return result


def rollback(task, plan, changed):
    errors = []
    for name, destination, existed in reversed(changed):
        try:
            if existed:
                replace_file(task / "backup" / name, destination)
            else:
                destination.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(str(exc))
    if errors:
        raise OSError("自动回退失败；备份保留于 " + str(task / "backup") + " · " + "; ".join(errors))


def install_files(task, plan):
    verify_payload(task, plan)
    pairs = destinations(task, plan)
    # Back up everything before changing a single installed file.
    changed = []
    for name, destination in pairs:
        existed = destination.exists()
        if existed:
            backup = task / "backup" / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup)
        changed.append((name, destination, existed))
    completed = []
    try:
        for name, destination, existed in changed:
            destination.parent.mkdir(parents=True, exist_ok=True)
            replace_file(task / "payload" / name, destination)
            completed.append((name, destination, existed))
    except Exception:
        rollback(task, plan, completed)
        raise
    return changed


def mark_healthy(plan_file):
    task = task_path(Path(plan_file).parent)
    if Path(plan_file).name != "plan.json":
        raise ValueError("更新启动参数无效")
    plan = json.loads((task / "plan.json").read_text(encoding="utf-8"))
    from . import VERSION
    if Path(sys.executable).resolve() != Path(plan["target"]) or VERSION != plan["version"]:
        raise ValueError("新版启动验证不匹配")
    atomic_json(task / "healthy.json", {"nonce": plan["nonce"]})


def helper_main(plan_file):
    task = task_path(Path(plan_file).parent)
    status = task / "status.json"
    kernel, handle, changed = None, None, []
    target = None
    original_exited = False
    try:
        if Path(plan_file).name != "plan.json":
            raise ValueError("更新参数无效")
        plan = json.loads((task / "plan.json").read_text(encoding="utf-8"))
        if plan.get("schema") != 1 or not re.fullmatch("[a-f0-9]{32}", plan.get("nonce", "")):
            raise ValueError("更新计划无效")
        target = Path(plan["target"])
        if target.resolve() != target or target.suffix.casefold() != ".exe":
            raise ValueError("目标程序路径无效")
        if (Path(sys.executable).resolve() != task / "update-helper.exe"
                or digest(sys.executable) != plan["old_sha256"] or digest(target) != plan["old_sha256"]):
            raise ValueError("更新助手只能更新与自身相同的原程序")
        kernel, handle = process_handle(plan["pid"], target)
        verify_payload(task, plan)
        destinations(task, plan)
        atomic_json(status, {"state": "ready"})
        if kernel.WaitForSingleObject(handle, 60000) != 0:
            raise TimeoutError("原程序尚未退出，取消安装")
        original_exited = True
        try:
            commit = json.loads((task / "commit.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            commit = {}
        if commit.get("nonce") != plan["nonce"]:
            atomic_json(status, {"state": "cancelled"})
            return 1
        atomic_json(status, {"state": "installing"})
        changed = install_files(task, plan)
        child = start_process([str(target), "--update-health", str(task / "plan.json")])
        end = time.monotonic() + 90
        while time.monotonic() < end:
            try:
                healthy = json.loads((task / "healthy.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                healthy = {}
            if healthy.get("nonce") == plan["nonce"]:
                atomic_json(status, {"state": "complete", "version": plan["version"]})
                return 0
            if child.poll() is not None:
                break
            time.sleep(.3)
        # Stop only the child we launched, never another running assistant.
        if child.poll() is None:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            child.wait(timeout=10)
        raise RuntimeError("新版未能正常启动，已回退旧版")
    except Exception as exc:
        message = str(exc)
        if changed:
            try:
                rollback(task, plan, changed)
            except OSError as rollback_error:
                message += "；" + str(rollback_error)
        atomic_json(status, {"state": "error", "message": message})
        if original_exited and target and target.is_file():
            start_process([str(target), "--update-result", str(task / "plan.json")])
        return 1
    finally:
        if handle:
            kernel.CloseHandle(handle)
