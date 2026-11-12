"""Non-blocking update controls; worker threads communicate only through a queue."""
import json
import logging
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import Event, Thread
import time
import tkinter as tk
from tkinter import ttk
import webbrowser

from . import VERSION
from .ui import BG, FG, SECONDARY, TEAL
from .update import REPOSITORY, atomic_json, check_release, download_release, version_tuple
from .update_install import prepare_install, start_process, task_path
from .update_session import save_session


class UpdateController:
    def __init__(self, app, directory, auto):
        self.app, self.root, self.directory = app, app.root, directory
        self.auto = tk.BooleanVar(value=auto)
        self.summary = tk.StringVar(value=f"当前版本 {VERSION} · 可检查更新")
        self.detail = tk.StringVar(value="后台检查只提示。下载并校验完成后，可选择安装并重启。")
        self.badge = tk.StringVar(value=f"v{VERSION}  /  检查更新")
        self.progress = tk.DoubleVar(value=0)
        self.events = Queue()
        self.cancel = Event()
        self.busy = False
        self.installing = False
        self.release = None
        self.task = None
        self.dialog = None
        self.action = None
        self.manual = False
        self.root.after(3500, self.periodic)
        self.root.after(150, self.poll)

    def periodic(self):
        if self.auto.get() and not self.busy and not self.task:
            self.check(False)
        self.root.after(6 * 60 * 60 * 1000, self.periodic)

    def worker(self, action):
        self.busy = True
        def run():
            try:
                kind, value = action()
                self.events.put((kind, value))
            except Exception as exc:
                logging.exception("Update operation failed")
                self.events.put(("error", str(exc)))
        Thread(target=run, daemon=True).start()

    def check(self, manual=True):
        if manual:
            self.show()
        if self.busy or self.task:
            return
        self.manual = manual
        self.summary.set("正在检查 GitHub 正式版本…")
        self.detail.set("检查在后台进行，可继续识别游戏。")
        self.worker(lambda: ("release", check_release()))
        self.render()

    def settings(self, parent):
        ttk.Separator(parent).pack(fill="x", pady=(16, 12))
        ttk.Label(parent, text="程序更新", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")
        ttk.Label(parent, textvariable=self.summary, foreground=TEAL).pack(anchor="w", pady=6)
        ttk.Checkbutton(parent, text="启动后及每 6 小时自动检查新版本", variable=self.auto,
                        command=self.app.save).pack(anchor="w")
        row = ttk.Frame(parent)
        row.pack(anchor="w", pady=6)
        ttk.Button(row, text="检查 / 管理更新", command=self.check).pack(side="left")
        ttk.Button(row, text="GitHub 发布页", command=lambda: webbrowser.open(REPOSITORY + "/releases"))\
            .pack(side="left", padx=8)
        ttk.Label(parent, text="自动检查仅提示；安装会重启助手。设置与自定义攻略保留。",
                  foreground=SECONDARY).pack(anchor="w", pady=4)

    def show(self):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        self.dialog = window = tk.Toplevel(self.root)
        window.title("程序更新 · 卫戍协议助手")
        window.configure(bg=BG)
        window.geometry("620x470")
        window.minsize(540, 430)
        body = ttk.Frame(window, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="程序更新", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(body, textvariable=self.summary, foreground=TEAL).pack(anchor="w", pady=(12, 5))
        ttk.Label(body, textvariable=self.detail, wraplength=550).pack(anchor="w", pady=(0, 12))
        self.notes = tk.Text(body, bg=BG, fg=FG, relief="flat", height=8, wrap="word",
                             font=("Microsoft YaHei UI", 10))
        self.notes.pack(fill="both", expand=True)
        ttk.Progressbar(body, variable=self.progress, maximum=100).pack(fill="x", pady=10)
        row = ttk.Frame(body)
        row.pack(fill="x")
        self.action = ttk.Button(row, text="检查更新", command=self.primary, style="Primary.TButton")
        self.action.pack(side="right")
        ttk.Button(row, text="发布详情", command=lambda: webbrowser.open(
            self.release.page if self.release else REPOSITORY + "/releases")).pack(side="left")
        self.cancel_button = ttk.Button(row, text="取消下载", command=self.cancel.set)
        self.cancel_button.pack(side="left", padx=8)
        window.protocol("WM_DELETE_WINDOW", self.hide)
        self.render()

    def hide(self):
        if self.dialog:
            self.dialog.destroy()
        self.dialog = self.action = None

    def render(self):
        if not self.action:
            return
        label = "安装并重启" if self.task else "下载更新" if self.release else "检查更新"
        self.action.configure(text=label, state="disabled" if self.busy else "normal")
        self.cancel_button.configure(state="normal" if self.busy and not self.installing and self.release
                                     else "disabled")
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", self.release.notes if self.release else
                          "正式更新来自本项目 GitHub Release，校验完整包后安装。\n"
                          "网络不可用时可稍后重试，当前版本仍可正常使用。")
        self.notes.configure(state="disabled")

    def primary(self):
        if self.busy:
            return
        if self.task:
            self.install()
        elif self.release:
            self.cancel.clear()
            self.progress.set(0)
            self.detail.set("正在下载并校验完整更新包，可继续使用助手。")
            last = [0.0]
            def progress(done, total):
                now = time.monotonic()
                if now - last[0] > .2 or done == total:
                    self.events.put(("progress", (done, total)))
                    last[0] = now
            self.worker(lambda: ("download", download_release(self.release, self.directory / "updates",
                                                               progress, self.cancel)))
            self.render()
        else:
            self.check()

    def install(self):
        if self.app.pc_pending:
            self.detail.set("请等待当前 PC 单步操作完成，再安装更新。")
            return
        if not getattr(sys, "frozen", False):
            self.detail.set("当前从源码运行。请使用发布页的 Windows 程序体验自动安装。")
            return
        self.installing = True
        self.detail.set("正在准备备份与更新助手；准备完成后将自动重启。")
        self.worker(lambda: ("prepared", prepare_install(self.task)))
        self.render()

    def wait_helper(self, deadline):
        try:
            status = json.loads((self.task / "status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            status = {}
        if status.get("state") == "ready":
            if self.app.pc_pending:
                self.fail("仍有 PC 单步操作正在执行，本次安装已取消")
                return
            try:
                self.app.save()
                if not self.app.preview:
                    save_session(self.app, self.task)
                plan = json.loads((self.task / "plan.json").read_text(encoding="utf-8"))
                atomic_json(self.task / "commit.json", {"nonce": plan["nonce"]})
            except Exception as exc:
                self.fail("保存当前状态失败：" + str(exc))
                return
            self.root.destroy()
            return
        if status.get("state") == "error":
            self.fail(status.get("message", "更新助手启动失败"))
            return
        if time.monotonic() > deadline:
            self.fail("更新助手启动超时；当前程序保持运行，请稍后重试")
            return
        self.root.after(200, lambda: self.wait_helper(deadline))

    def fail(self, message):
        self.busy = self.installing = False
        self.summary.set(f"当前版本 {VERSION} · 更新未完成")
        self.detail.set(message + "。可重试或通过发布页下载。")
        self.render()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    done, total = value
                    self.progress.set(done / total * 100)
                    self.detail.set(f"已下载 {done / 1024**2:.1f} / {total / 1024**2:.1f} MB · 完成后自动校验")
                    continue
                self.busy = False
                if kind == "release":
                    logging.info("Update check succeeded: latest=%s current=%s", value.version, VERSION)
                    if version_tuple(value.version) > version_tuple(VERSION):
                        self.release = value
                        self.summary.set(f"发现新版本 {value.version} · 当前 {VERSION}")
                        self.badge.set(f"新版本 {value.version}  /  查看更新")
                        self.detail.set("可以先下载，等本局结束后再安装。安装会关闭并重启助手。")
                    else:
                        self.summary.set(f"当前版本 {VERSION} · 已是最新正式版")
                        self.detail.set("暂时没有更新；可继续使用。")
                elif kind == "download":
                    self.task = value
                    self.detail.set("下载与 SHA-256 校验完成。安装将备份旧文件并重启助手。")
                    self.progress.set(100)
                elif kind == "prepared":
                    try:
                        start_process([str(self.task / "update-helper.exe"), "--apply-update",
                                       str(self.task / "plan.json")])
                        self.busy = True
                        self.root.after(200, lambda: self.wait_helper(time.monotonic() + 60))
                    except OSError as exc:
                        self.fail(str(exc))
                elif kind == "error":
                    self.fail(value)
                self.render()
        except Empty:
            pass
        self.root.after(150, self.poll)


def complete_startup(app, plan_file=None, result_file=None):
    if plan_file or result_file:
        path = Path(plan_file or result_file)
        try:
            task_path(path.parent)
            from .update_session import restore_session
            if (path.parent / "session.json").is_file():
                restore_session(app, path)
            if result_file:
                result = json.loads((path.parent / "status.json").read_text(encoding="utf-8"))
                app.updater.fail(result.get("message", "更新失败，旧版已恢复"))
                app.updater.show()
            else:
                from .update_install import mark_healthy
                app.root.after(1200, lambda: mark_healthy(path))
        except Exception:
            logging.exception("Cannot restore update startup")
