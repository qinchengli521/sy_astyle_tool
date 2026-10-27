# -*- coding: utf-8 -*-
"""Astyle 批量格式化工具 —— 界面层（tkinter / 纯标准库）。

层次约定：
- 本文件只负责"看得见的部分"：控件搭建、界面原语（选文件、改文本、写日志、
  弹窗、读写 settings.ini）。**不绑定业务命令**——所有按钮/菜单的命令与事件
  都在 main.py 的 AppController 里注册（`widget.configure(command=...)`）。
- 视图内部机制（占位提示、滚动条、日志着色）留在本文件，属纯界面细节。
- closeEvent 这类窗口事件也不在这里处理，由 main.py 通过 `protocol()` 注册。
"""

from __future__ import annotations

import configparser
import os
import re
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List

DEFAULT_EXE = r"D:\astyle\astyle.exe"
DEFAULT_RC = r"D:\astyle\.astylerc"
LOG_DIR = Path(__file__).resolve().parent / "logs"
SETTINGS_FILE = Path(__file__).resolve().parent / "settings.ini"

LOG_COLORS = {
    "OK": "#1a7f37",
    "SKIP": "#6e7781",
    "FAIL": "#cf222e",
    "INFO": "#24292f",
}
HINT_COLOR = "#8a8f98"

ALL_EXTS = [".c", ".h", ".cpp", ".hpp"]
DEFAULT_EXTS = [".c", ".h"]

WINDOW_TITLE = "思远Astyle代码风格化工具 V0.1"
WINDOW_GEOMETRY = "610x620"
MIN_WIDTH, MIN_HEIGHT = 610, 620

EXT_VARS = {
    ".c": "ext_c_var",
    ".h": "ext_h_var",
    ".cpp": "ext_cpp_var",
    ".hpp": "ext_hpp_var",
}

GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


class Settings:
    """settings.ini 读写（configparser，无插值）。

    键名与旧版 QSettings 版本保持一致：exe/rc/root/recursive/backup/dry_run/
    exts/excludes/history/geometry。[General] 段。
    """

    SECTION = "General"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.parser = configparser.ConfigParser(interpolation=None)
        if self.path.exists():
            try:
                self.parser.read(self.path, encoding="utf-8")
            except (OSError, configparser.Error):
                pass
        if not self.parser.has_section(self.SECTION):
            self.parser.add_section(self.SECTION)

    def get(self, key: str, default: str = "") -> str:
        raw = self.parser.get(self.SECTION, key, fallback=None)
        if raw is None:
            return default
        raw = raw.strip()
        # 兼容旧 QSettings 写入的带引号值（如 exts=".c,.h"）
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            raw = raw[1:-1]
        return raw

    def get_path(self, key: str, default: str = "") -> str:
        """路径类取值：额外还原旧 QSettings 的双写反斜杠（D:\\\\astyle → D:\\astyle）。"""
        raw = self.get(key, default)
        return raw.replace("\\\\", "\\") if "\\\\" in raw else raw

    def get_bool(self, key: str, default: bool) -> bool:
        raw = self.get(key, "").strip().lower()
        if not raw:
            return default
        return raw in ("1", "true", "yes", "on")

    def set(self, key: str, value) -> None:
        if isinstance(value, bool):
            value = "true" if value else "false"
        self.parser.set(self.SECTION, key, str(value))

    def sync(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
                self.parser.write(fh, space_around_delimiters=True)
        except OSError:
            pass


def read_text_any(path: Path) -> str:
    """尽力解码文本文件（utf-8 优先，回退 gbk）。"""
    data = path.read_bytes()
    for enc in ("utf-8-sig", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


class PlaceholderEntry(tk.Entry):
    """带灰色占位提示的输入框（tk 没有内建 placeholder）。"""

    def __init__(self, master=None, hint: str = "", width: int = 1, **kwargs):
        super().__init__(master, width=width, relief="solid", bd=1, **kwargs)
        self._var = tk.StringVar()
        self.configure(textvariable=self._var)
        self._hint = hint
        self._hint_shown = False
        self._normal_color = self.cget("fg")
        self._show_hint()
        self.bind("<FocusIn>", self._on_focus_in, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")

    def _show_hint(self):
        if not self._hint_shown and not self._var.get().strip() and self._hint:
            self._hint_shown = True
            self._var.set(self._hint)
            self.configure(fg=HINT_COLOR)

    def _hide_hint(self):
        if self._hint_shown:
            self._hint_shown = False
            self._var.set("")
            self.configure(fg=self._normal_color)

    def _on_focus_in(self, _event=None):
        self._hide_hint()

    def _on_focus_out(self, _event=None):
        self._show_hint()

    def get_text(self) -> str:
        return "" if self._hint_shown else self._var.get()

    def set_text(self, value: str):
        self._hint_shown = False
        self._var.set(value)
        self.configure(fg=self._normal_color)
        self._show_hint()


class MainWindow(tk.Tk):
    """主窗口：只搭界面并暴露界面原语，不绑定任何业务命令。"""

    def __init__(self):
        super().__init__()
        self.settings = Settings(SETTINGS_FILE)
        self._running = False

        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_GEOMETRY)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

        self._init_style()
        self._build_ui()
        self.set_status("就绪")

    # ------------------------------------------------------------------ 样式
    def _init_style(self):
        style = ttk.Style(self)
        base = tkfont.nametofont("TkDefaultFont")
        family, size = base.actual("family"), base.actual("size")
        style.configure("TLabelframe.Label", font=(family, size, "bold"))
        style.configure("TButton", padding=(8, 3))
        style.configure("TLabel", padding=(0, 1))

    # ------------------------------------------------------------------ 布局
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        # --- 路径设置 ---
        path = ttk.LabelFrame(self, text="路径设置", padding=(8, 6))
        path.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        path.columnconfigure(1, weight=1)

        ttk.Label(path, text="Astyle 程序", width=11, anchor="w").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.exe_edit = PlaceholderEntry(
            path, hint=r"astyle.exe 完整路径，例如 D:\astyle\astyle.exe"
        )
        self.exe_edit.grid(row=0, column=1, sticky="ew", pady=2)
        self.btn_exe = ttk.Button(path, text="浏览", width=6)
        self.btn_exe.grid(row=0, column=2, padx=(6, 3), pady=2)
        self.btn_check = ttk.Button(path, text="检测", width=6)
        self.btn_check.grid(row=0, column=3, pady=2)

        ttk.Label(path, text="风格配置", width=11, anchor="w").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.rc_edit = PlaceholderEntry(
            path, hint=r"风格配置文件路径，例如 D:\astyle\.astylerc"
        )
        self.rc_edit.grid(row=1, column=1, sticky="ew", pady=2)
        self.btn_rc = ttk.Button(path, text="浏览", width=6)
        self.btn_rc.grid(row=1, column=2, padx=(6, 3), pady=2)
        self.btn_rc_view = ttk.Button(path, text="查看", width=6)
        self.btn_rc_view.grid(row=1, column=3, pady=2)

        ttk.Label(path, text="代码目录", width=11, anchor="w").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.dir_edit = PlaceholderEntry(
            path, hint="需要格式化的代码目录（点“浏览”选择）"
        )
        self.dir_edit.grid(row=2, column=1, sticky="ew", pady=2)
        self.btn_dir = ttk.Button(path, text="浏览", width=6)
        self.btn_dir.grid(row=2, column=2, padx=(6, 3), pady=2)
        self.btn_history = ttk.Button(path, text="历史", width=6)
        self.btn_history.grid(row=2, column=3, pady=2)

        # --- 选项 ---
        opt = ttk.LabelFrame(self, text="选项", padding=(8, 6))
        opt.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        opt.columnconfigure(1, weight=1)

        self.recursive_var = tk.BooleanVar(value=True)
        self.chk_recursive = ttk.Checkbutton(
            opt, text="递归子目录", variable=self.recursive_var
        )
        self.chk_recursive.grid(row=0, column=0, sticky="w", pady=2)

        self.backup_var = tk.BooleanVar(value=True)
        self.chk_backup = ttk.Checkbutton(
            opt, text="保留 .orig 备份", variable=self.backup_var
        )
        self.chk_backup.grid(row=0, column=1, sticky="w", padx=(14, 0), pady=2)

        self.dryrun_var = tk.BooleanVar(value=False)
        self.chk_dryrun = ttk.Checkbutton(
            opt, text="预览模式（不改文件）", variable=self.dryrun_var
        )
        self.chk_dryrun.grid(row=0, column=2, sticky="w", padx=(14, 0), pady=2)

        ttk.Label(opt, text="文件类型", width=11, anchor="w").grid(
            row=1, column=0, sticky="w", pady=2
        )
        ext_row = ttk.Frame(opt)
        ext_row.grid(row=1, column=1, columnspan=2, sticky="w")
        self.ext_vars: dict[str, tk.BooleanVar] = {}
        self.ext_boxes: dict[str, ttk.Checkbutton] = {}
        for index, ext in enumerate(ALL_EXTS):
            var = tk.BooleanVar(value=ext in DEFAULT_EXTS)
            box = ttk.Checkbutton(ext_row, text=ext, variable=var)
            box.pack(side="left", padx=(0, 10))
            self.ext_vars[ext] = var
            self.ext_boxes[ext] = box

        ttk.Label(opt, text="排除目录", width=11, anchor="w").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.exclude_edit = PlaceholderEntry(
            opt, hint="排除的目录，多个用 ; 分隔，例如 build;output;third_party"
        )
        self.exclude_edit.grid(row=2, column=1, sticky="ew", pady=2)
        self.btn_add_exclude = ttk.Button(opt, text="添加", width=6)
        self.btn_add_exclude.grid(row=2, column=2, padx=(6, 0), pady=2)

        # --- 操作 ---
        act = ttk.LabelFrame(self, text="操作", padding=(8, 6))
        act.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.btn_start = ttk.Button(act, text="开始风格化", width=12)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(act, text="停止", width=6, state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 14))
        self.btn_clear = ttk.Button(act, text="清空日志", width=9)
        self.btn_clear.pack(side="left")
        self.btn_open_log = ttk.Button(act, text="打开日志目录", width=12)
        self.btn_open_log.pack(side="left", padx=(6, 0))
        self.btn_clean_orig = ttk.Button(act, text="清理.orig备份", width=13)
        self.btn_clean_orig.pack(side="left", padx=(6, 0))

        # --- 进度 ---
        prog = ttk.LabelFrame(self, text="进度", padding=(8, 6))
        prog.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        prog.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(prog, mode="determinate", maximum=1, value=0)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress_label = ttk.Label(prog, text="0 / 0", width=8, anchor="e")
        self.progress_label.grid(row=0, column=1, padx=(8, 0))

        # --- 日志 ---
        log_frame = ttk.Frame(self)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_edit = tk.Text(
            log_frame,
            wrap="none",
            font=tkfont.Font(family="Consolas", size=10),
            bg="#ffffff",
            bd=1,
            relief="solid",
            highlightthickness=0,
            state="disabled",
        )
        vbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_edit.yview)
        hbar = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log_edit.xview)
        self.log_edit.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.log_edit.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        for level, color in LOG_COLORS.items():
            self.log_edit.tag_configure(level, foreground=color)

        # --- 状态栏 ---
        self.status_label = ttk.Label(self, text="就绪", anchor="w", padding=(10, 3))
        self.status_label.grid(row=5, column=0, sticky="ew")

    # ------------------------------------------------- 界面原语：读取/设置输入
    def exe_path(self) -> str:
        return self.exe_edit.get_text().strip().strip('"')

    def rc_path(self) -> str:
        return self.rc_edit.get_text().strip().strip('"')

    def code_dir(self) -> str:
        return self.dir_edit.get_text().strip().strip('"')

    def set_code_dir(self, path: str):
        self.dir_edit.set_text(path)

    def get_config(self) -> dict:
        return {
            "exe": self.exe_path(),
            "rc": self.rc_path(),
            "root": self.code_dir(),
            "recursive": self.recursive_var.get(),
            "backup": self.backup_var.get(),
            "dry_run": self.dryrun_var.get(),
            "extensions": [e for e, var in self.ext_vars.items() if var.get()],
            "excludes": [
                s.strip().strip('"')
                for s in self.exclude_edit.get_text().split(";")
                if s.strip()
            ],
        }

    # ------------------------------------------------- 界面原语：选择文件/目录
    def pick_exe(self) -> str:
        return self._pick_file(
            self.exe_edit,
            "选择 astyle.exe",
            [("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )

    def pick_rc(self) -> str:
        return self._pick_file(
            self.rc_edit,
            "选择风格配置文件",
            [("astyle 配置", "*.astylerc"), ("所有文件", "*.*")],
        )

    def pick_code_dir(self) -> str:
        path = self._pick_dir_dialog("选择代码目录", self.code_dir())
        if path:
            self.set_code_dir(path)
        return path

    def pick_exclude_dir(self) -> str:
        """只返回用户选中的目录，如何并入排除列表由 main.py 决定。"""
        return self._pick_dir_dialog("选择要排除的目录", self.code_dir())

    def _pick_file(self, entry: PlaceholderEntry, title: str, filetypes) -> str:
        start = entry.get_text().strip().strip('"')
        initial = str(Path(start).parent) if start and Path(start).parent.is_dir() else ""
        path = filedialog.askopenfilename(
            parent=self, title=title, initialdir=initial or None, filetypes=filetypes
        )
        if not path:
            return ""
        path = os.path.normpath(path)
        entry.set_text(path)
        return path

    def _pick_dir_dialog(self, title: str, start: str) -> str:
        initial = start if start and Path(start).is_dir() else str(Path.home())
        path = filedialog.askdirectory(parent=self, title=title, initialdir=initial)
        return os.path.normpath(path) if path else ""

    def append_exclude(self, path: str):
        """把目录并入排除列表；位于代码目录内时存相对路径。"""
        items = [
            s.strip() for s in self.exclude_edit.get_text().split(";") if s.strip()
        ]
        code_dir = self.code_dir()
        if code_dir:
            try:
                path = str(Path(path).resolve().relative_to(Path(code_dir).resolve()))
            except (ValueError, OSError):
                pass
        if path not in items:
            items.append(path)
        self.exclude_edit.set_text(";".join(items))

    # ------------------------------------------------- 界面原语：回收处理结果
    def append_log(self, text: str, level: str = "INFO"):
        tag = level if level in LOG_COLORS else "INFO"
        self.log_edit.configure(state="normal")
        self.log_edit.insert("end", text + "\n", tag)
        self.log_edit.see("end")
        self.log_edit.configure(state="disabled")

    def clear_log(self):
        self.log_edit.configure(state="normal")
        self.log_edit.delete("1.0", "end")
        self.log_edit.configure(state="disabled")

    def set_progress(self, done: int, total: int):
        self.progress.configure(maximum=max(total, 1), value=min(done, max(total, 1)))
        self.progress_label.configure(text=f"{done} / {total}")

    def set_running(self, running: bool):
        self._running = running
        state = "disabled" if running else "normal"
        self.btn_start.configure(state=state)
        self.btn_check.configure(state=state)
        self.btn_clean_orig.configure(state=state)
        self.btn_stop.configure(state="normal" if running else "disabled")
        if running:
            self.set_status("处理中…")
        else:
            self.progress.configure(value=0)

    def set_status(self, text: str):
        self.status_label.configure(text=text)

    def set_summary(self, stat: dict):
        head = "已停止" if stat.get("stopped") else "完成"
        self.set_status(
            f"状态：{head}    处理：{stat.get('total', 0)}    已改：{stat.get('ok', 0)}    "
            f"无变化：{stat.get('skip', 0)}    失败：{stat.get('fail', 0)}    "
            f"用时：{stat.get('elapsed', 0.0):.2f}s"
        )

    # ------------------------------------------------- 界面原语：弹窗
    def notify(self, title: str, text: str, level: str = "info", show_log_button: bool = False):
        """系统消息框（show_log_button 仅为兼容旧调用，tk 版不提供额外按钮）。"""
        show = {
            "info": messagebox.showinfo,
            "warning": messagebox.showwarning,
            "error": messagebox.showerror,
        }.get(level, messagebox.showinfo)
        show(title, text, parent=self)

    def ask_confirm(self, title: str, text: str) -> bool:
        return bool(messagebox.askyesno(title, text, parent=self))

    def open_log_dir(self):
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(LOG_DIR))
        except OSError as exc:
            self.notify("打开日志目录", f"无法打开：\n{exc}", "warning")

    # -------------------------------------------------------------- 持久化
    def save_settings(self):
        s = self.settings
        s.set("exe", self.exe_edit.get_text())
        s.set("rc", self.rc_edit.get_text())
        s.set("root", self.dir_edit.get_text())
        s.set("recursive", self.recursive_var.get())
        s.set("backup", self.backup_var.get())
        s.set("dry_run", self.dryrun_var.get())
        s.set("exts", ",".join(e for e, var in self.ext_vars.items() if var.get()))
        s.set("excludes", self.exclude_edit.get_text())
        s.set("geometry", self.winfo_geometry())
        s.sync()

    def load_settings(self):
        s = self.settings
        self.exe_edit.set_text(s.get_path("exe", DEFAULT_EXE))
        self.rc_edit.set_text(s.get_path("rc", DEFAULT_RC))
        self.dir_edit.set_text(s.get_path("root", ""))
        self.recursive_var.set(s.get_bool("recursive", True))
        self.backup_var.set(s.get_bool("backup", True))
        self.dryrun_var.set(s.get_bool("dry_run", False))

        exts = s.get("exts", ",".join(DEFAULT_EXTS))
        chosen = {e.strip() for e in exts.split(",") if e.strip()}
        for ext, var in self.ext_vars.items():
            var.set(ext in chosen)

        self.exclude_edit.set_text(s.get_path("excludes", ""))

        geometry = s.get("geometry", "")
        if GEOMETRY_RE.match(geometry):
            self.geometry(geometry)
