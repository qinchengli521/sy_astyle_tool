# -*- coding: utf-8 -*-
"""Astyle 批量格式化工具 —— 入口与业务逻辑。

与 Source Insight 脚本等价：
    "D:\\astyle\\astyle.exe" --options="D:\\astyle\\.astylerc" 目标文件
本程序逐文件调用 astyle，风格完全来自 .astylerc，不额外施加任何风格参数。

分层约定：
- 界面在 main_window.ui → ui_main_window.py → ui_main.py（只做展示，不连信号）。
- **全部信号槽连接都在本文件的 AppController 里**，包括浏览按钮、清空日志、
  打开日志目录、历史目录菜单等界面内动作。
- 本文件只通过 MainWindow 的公开方法/属性操作界面，不直接改控件状态。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# PyQt6 6.4.x 的 sip 在"用 Python 继承 Qt 类"（QMainWindow / QThread 子类）实例化时
# 仍会发出 "sipPyTypeDict() is deprecated ... " 的 DeprecationWarning：
# 是 sip 扩展自身的问题，与本程序无关，也无法通过改代码消除
# （PyQt6 ≥ 6.5 已修复）。这里定向屏蔽，避免污染控制台输出。
# 注意：警告在实例化时才发出，但为保险起见仍在导入 PyQt6 之前设置。
warnings.filterwarnings(
    "ignore",
    message=r"sipPyTypeDict\(\) is deprecated.*",
    category=DeprecationWarning,
)

from PyQt6.QtCore import Qt, QThread, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ui_main import LOG_DIR, MainWindow, read_text_any  # noqa: E402

TIMEOUT = 60  # 单文件超时（秒）
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

HISTORY_KEY = "history"     # 历史代码目录，存 settings.ini，JSON 数组，最近的在前
HISTORY_LIMIT = 10          # 最多保留条数


# ---------------------------------------------------------------- 基础工具
def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def decode_output(data: bytes) -> str:
    """astyle 在中文 Windows 下可能输出 GBK，做多编码回退。"""
    if not data:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def build_argv(exe: str, rc: str, target: Path) -> List[str]:
    # --suffix=none：备份由本程序负责，避免 astyle 再生成一份 .orig
    return [exe, f"--options={rc}", "--suffix=none", str(target)]


def run_astyle(exe: str, rc: str, target: Path, timeout: int = TIMEOUT) -> Tuple[int, str]:
    """执行一次 astyle，返回 (退出码, 单行化后的输出)。退出码 <0 表示本程序层面的失败。"""
    try:
        proc = subprocess.run(
            build_argv(exe, rc, target),
            shell=False,
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return -1, f"执行超时（超过 {timeout} 秒）"
    except OSError as exc:
        return -2, f"无法启动 astyle：{exc}"

    output = decode_output(proc.stdout) + decode_output(proc.stderr)
    output = " ".join(output.split())
    if len(output) > 300:
        output = output[:300] + "..."
    return proc.returncode, output


def orig_path(path: Path) -> Path:
    """<文件名>.orig 的路径。"""
    return path.with_name(path.name + ".orig")


def backup_file(path: Path) -> Tuple[str, str]:
    """把源文件复制为 文件名.orig（已有旧备份则直接覆盖）。返回 (状态, 说明)。"""
    try:
        shutil.copy2(path, orig_path(path))
    except OSError as exc:
        return "FAIL", f"备份失败：{exc}"
    return "OK", "已备份"


# ---------------------------------------------------------------- 文件扫描
def _is_excluded_path(path: Path, excludes: List[Path]) -> bool:
    try:
        target = str(path.resolve()).lower()
    except OSError:
        target = str(path).lower()
    for item in excludes:
        base = str(item).lower()
        if target == base or target.startswith(base + os.sep):
            return True
    return False


def scan_files(
    root: Path, extensions: List[str], recursive: bool, excludes: List[str]
) -> Tuple[List[Path], int]:
    """返回 (待处理文件列表, 被排除的目录数)。"""
    exts = {e.lower() for e in extensions}
    names: set[str] = set()
    paths: List[Path] = []
    for raw in excludes:
        item = raw.strip()
        if not item:
            continue
        if os.path.isabs(item) or ("/" in item) or ("\\" in item):
            candidate = Path(item)
            if not candidate.is_absolute():
                candidate = root / candidate
            paths.append(candidate)
        else:
            names.add(item.lower())

    files: List[Path] = []
    excluded_dirs = 0

    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            keep = []
            for name in sorted(dirnames):
                full = Path(dirpath) / name
                if name.lower() in names or (paths and _is_excluded_path(full, paths)):
                    excluded_dirs += 1
                else:
                    keep.append(name)
            dirnames[:] = keep
            for name in filenames:
                full = Path(dirpath) / name
                if full.suffix.lower() in exts:
                    files.append(full)
    else:
        for entry in root.iterdir():
            if entry.is_file() and entry.suffix.lower() in exts:
                files.append(entry)

    files.sort(key=lambda p: str(p).lower())
    return files, excluded_dirs


def scan_orig_files(root: Path, recursive: bool) -> List[Path]:
    """收集以 .orig 结尾的备份文件。"""
    walker = root.rglob("*") if recursive else root.glob("*")
    targets = [p for p in walker if p.is_file() and p.name.lower().endswith(".orig")]
    targets.sort(key=lambda p: str(p).lower())
    return targets


# ---------------------------------------------------------------- 校验
def validate_config(cfg: dict) -> Optional[str]:
    if not cfg["exe"]:
        return "请先指定 astyle.exe 的路径。"
    exe = Path(cfg["exe"])
    if not exe.is_file():
        return f"astyle 程序不存在：\n{exe}"

    if not cfg["rc"]:
        return "请先指定 .astylerc 风格配置文件的路径。"
    rc = Path(cfg["rc"])
    if not rc.is_file():
        return f"风格配置文件不存在：\n{rc}"

    if not cfg["root"]:
        return "请先指定需要格式化的代码目录。"
    root = Path(cfg["root"])
    if not root.is_dir():
        return f"代码目录不存在：\n{root}"

    if not cfg["extensions"]:
        return "请至少勾选一种文件类型。"
    return None


# ---------------------------------------------------------------- 后台任务
class FormatWorker(QThread):
    log_signal = pyqtSignal(str, str)      # (整行文本, 级别)
    progress_signal = pyqtSignal(int, int)  # (已完成, 总数)
    done_signal = pyqtSignal(dict)          # 统计结果

    def __init__(self, job: dict, parent=None):
        super().__init__(parent)
        self.job = job
        self._stop = False

    def request_stop(self):
        self._stop = True

    def run(self):
        files: List[Path] = self.job["files"]
        root: Path = self.job["root"]
        exe, rc = self.job["exe"], self.job["rc"]
        dry = self.job["dry_run"]
        total = len(files)

        stat = {
            "total": total,
            "ok": 0,
            "skip": 0,
            "fail": 0,
            "stopped": False,
            "dry_run": dry,
            "elapsed": 0.0,
        }
        started = time.perf_counter()
        tmpdir = tempfile.mkdtemp(prefix="astyle_preview_") if dry else ""

        try:
            for index, path in enumerate(files, 1):
                if self._stop:
                    stat["stopped"] = True
                    break

                begin = time.perf_counter()
                if dry:
                    status, message = self._preview_one(exe, rc, path, tmpdir)
                else:
                    status, message = self._process_one(exe, rc, path)
                cost = time.perf_counter() - begin

                if status == "OK":
                    stat["ok"] += 1
                elif status == "FAIL":
                    stat["fail"] += 1
                else:
                    stat["skip"] += 1

                line = f"[{now_ts()}] [{status:<4}] {rel_path(path, root)}  {message}  {cost:.2f}s"
                self.log_signal.emit(line, status)
                self.progress_signal.emit(index, total)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

        stat["elapsed"] = time.perf_counter() - started
        self.done_signal.emit(stat)

    # 实际格式化
    def _process_one(self, exe: str, rc: str, path: Path) -> Tuple[str, str]:
        backed_up = False
        if self.job["backup"]:
            state, note = backup_file(path)
            if state == "FAIL":
                return "FAIL", note
            backed_up = True

        try:
            before = sha256_file(path)
        except OSError as exc:
            return "FAIL", f"读取失败：{exc}"

        code, output = run_astyle(exe, rc, path)
        if code != 0:
            return "FAIL", f"退出码 {code}" + (f"：{output}" if output else "")

        try:
            after = sha256_file(path)
        except OSError as exc:
            return "FAIL", f"格式化后读取失败：{exc}"

        if before != after:
            return "OK", "已格式化"

        # 无变化：备份内容与源文件完全相同，留着只会堆积垃圾，删掉
        if backed_up:
            try:
                orig_path(path).unlink()
            except OSError as exc:
                return "SKIP", f"无变化（备份删除失败：{exc}）"
            return "SKIP", "无变化（已删除备份）"
        return "SKIP", "无变化"

    # 预览：在临时副本上真实格式化，比较哈希，原文件不动
    @staticmethod
    def _preview_one(exe: str, rc: str, path: Path, tmpdir: str) -> Tuple[str, str]:
        tmp = Path(tmpdir) / path.name
        try:
            shutil.copy2(path, tmp)
            before = sha256_file(tmp)
            code, output = run_astyle(exe, rc, tmp)
            if code != 0:
                return "FAIL", f"退出码 {code}" + (f"：{output}" if output else "")
            after = sha256_file(tmp)
            return ("OK", "将会修改") if before != after else ("SKIP", "无需修改")
        except OSError as exc:
            return "FAIL", f"预览失败：{exc}"
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass


class LogFile:
    """追加写入 logs/astyle_YYYYMMDD_HHMMSS.log（UTF-8 带 BOM，记事本可读）。"""

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        name = datetime.now().strftime("astyle_%Y%m%d_%H%M%S.log")
        self.path = LOG_DIR / name
        self._fh = open(self.path, "w", encoding="utf-8-sig", newline="\n")

    def write(self, line: str):
        if self._fh:
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None


# ---------------------------------------------------------------- 控制器
class AppController:
    def __init__(self, window: MainWindow):
        self.window = window
        self.worker: Optional[FormatWorker] = None
        self.logger: Optional[LogFile] = None
        self.pending_close = False
        self.job: dict = {}

        self._connect_signals()

    # -------- 所有信号槽集中在这里（ui_main.py 不含任何 connect）
    def _connect_signals(self):
        w = self.window

        # 路径选择
        w.btn_exe.clicked.connect(self.on_pick_exe)
        w.btn_rc.clicked.connect(self.on_pick_rc)
        w.btn_rc_view.clicked.connect(self.on_view_rc)
        w.btn_dir.clicked.connect(self.on_pick_code_dir)
        w.btn_add_exclude.clicked.connect(self.on_add_exclude)

        # 日志与工具
        w.btn_clear.clicked.connect(w.clear_log)
        w.btn_open_log.clicked.connect(w.open_log_dir)

        # 主流程
        w.btn_check.clicked.connect(self.on_check)
        w.btn_start.clicked.connect(self.on_start)
        w.btn_stop.clicked.connect(self.on_stop)
        w.btn_clean_orig.clicked.connect(self.on_clean_orig)
        w.close_requested.connect(self.on_close_requested)

        # 历史目录：QToolButton + InstantPopup，点一下弹菜单，弹出前重建内容
        self.history_menu = QMenu(w)
        self.history_menu.aboutToShow.connect(self.refresh_history_menu)
        w.btn_history.setMenu(self.history_menu)
        self.refresh_history_menu()

    # -------- 浏览按钮
    def on_pick_exe(self):
        path = self.window.pick_exe()
        if path:
            self.window.set_status(f"已选择 astyle：{path}")

    def on_pick_rc(self):
        path = self.window.pick_rc()
        if path:
            self.window.set_status(f"已选择风格配置：{path}")

    def on_view_rc(self):
        p = Path(self.window.rc_path())
        if not p.is_file():
            self.window.notify("查看风格配置", f"文件不存在：\n{p}", "warning")
            return
        try:
            text = read_text_any(p)
        except OSError as exc:
            self.window.notify("查看风格配置", f"读取失败：\n{exc}", "warning")
            return
        self._show_text_dialog(f"风格配置（只读） - {p.name}", str(p), text)

    def _show_text_dialog(self, title: str, subtitle: str, text: str):
        """只读文本对话框（查看 .astylerc 用），由业务层构造并连接其按钮。"""
        dlg = QDialog(self.window)
        dlg.setWindowTitle(title)
        dlg.resize(760, 640)
        lay = QVBoxLayout(dlg)
        hint = QLabel(subtitle)
        hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        edit = QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(text)
        edit.setFont(QFont("Consolas", 10))
        edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(hint)
        lay.addWidget(edit, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("关闭")
        btn.clicked.connect(dlg.accept)
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec()

    def on_pick_code_dir(self):
        path = self.window.pick_code_dir()
        if path:
            self.remember_dir(path)
            self.window.set_status(f"已选择代码目录：{path}")

    def on_add_exclude(self):
        path = self.window.pick_exclude_dir()
        if path:
            self.window.append_exclude(path)

    # -------- 历史目录（数据落在 settings.ini 的 history 键，JSON 数组）
    def history(self) -> List[str]:
        raw = self.window.settings.value(HISTORY_KEY, "", type=str)
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(items, list):
            return []
        return [p for p in items if isinstance(p, str) and p]

    def save_history(self, items: List[str]):
        self.window.settings.setValue(
            HISTORY_KEY, json.dumps(items[:HISTORY_LIMIT], ensure_ascii=False)
        )
        self.window.settings.sync()

    def remember_dir(self, path: str):
        """记录使用过的代码目录：去重、最近的在最前、最多 HISTORY_LIMIT 条。"""
        text = (path or "").strip().strip('"')
        if not text or not Path(text).is_dir():
            return
        try:
            norm = str(Path(text).resolve())
        except OSError:
            norm = os.path.normpath(text)
        key = os.path.normcase(norm)
        items = [norm] + [
            p for p in self.history() if os.path.normcase(os.path.normpath(p)) != key
        ]
        self.save_history(items)

    def refresh_history_menu(self):
        menu = self.history_menu
        menu.clear()
        entries = [p for p in self.history() if Path(p).is_dir()]
        if not entries:
            menu.addAction("（暂无历史目录，先浏览一次目录）").setEnabled(False)
            return
        for path in entries:
            action = menu.addAction(f"{Path(path).name}    {path}")
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, target=path: self.on_history_chosen(target)
            )
        menu.addSeparator()
        menu.addAction("清除历史记录").triggered.connect(self.on_clear_history)

    def on_history_chosen(self, path: str):
        self.window.set_code_dir(path)
        self.remember_dir(path)
        self.window.set_status(f"已切换代码目录：{path}")

    def on_clear_history(self):
        self.save_history([])
        self.window.set_status("已清除历史目录")

    # -------- 日志同时进界面和文件
    def _log(self, line: str, level: str = "INFO"):
        self.window.append_log(line, level)
        if self.logger:
            self.logger.write(line)

    def _close_logger(self):
        if self.logger:
            self.logger.close()
            self.logger = None

    # -------- 检测 astyle 可执行性
    def on_check(self):
        exe = self.window.exe_path()
        if not exe:
            self.window.notify("检测 astyle", "请先填写 astyle.exe 的路径。", "warning")
            return
        if not Path(exe).is_file():
            self.window.notify("检测 astyle", f"文件不存在：\n{exe}", "warning")
            return
        try:
            proc = subprocess.run(
                [exe, "--version"],
                shell=False,
                capture_output=True,
                timeout=15,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.window.notify("检测 astyle", f"无法执行：\n{exc}", "error")
            return

        output = " ".join((decode_output(proc.stdout) + decode_output(proc.stderr)).split())
        if proc.returncode == 0 and output:
            msg = f"检测成功：{output}"
            self.window.set_status(msg)
            self._log(f"[{now_ts()}] [INFO] {msg}", "INFO")
        else:
            msg = f"检测失败（退出码 {proc.returncode}）{('：' + output) if output else ''}"
            self.window.notify("检测 astyle", msg, "warning")

    # -------- 清理代码目录下的 .orig 备份
    def on_clean_orig(self):
        if self.worker and self.worker.isRunning():
            return

        cfg = self.window.get_config()
        root_text = (cfg.get("root") or "").strip()
        if not root_text:
            self.window.notify("清理备份", "请先指定代码目录。", "warning")
            return
        root = Path(root_text)
        if not root.is_dir():
            self.window.notify("清理备份", f"代码目录不存在：\n{root}", "warning")
            return

        recursive = bool(cfg.get("recursive"))
        targets = scan_orig_files(root, recursive)
        if not targets:
            self.window.notify("清理备份", "该目录下没有 .orig 备份文件。", "info")
            return

        scope = "含所有子目录" if recursive else "仅当前目录"
        if not self.window.ask_confirm(
            "清理 .orig 备份",
            f"将删除 {len(targets)} 个 .orig 备份文件（{scope}）：\n{root}\n\n删除后无法恢复，是否继续？",
        ):
            return

        removed = 0
        failed = 0
        for path in targets:
            try:
                path.unlink()
                removed += 1
                self._log(f"[{now_ts()}] [INFO] 已删除 {rel_path(path, root)}", "INFO")
            except OSError as exc:
                failed += 1
                self._log(f"[{now_ts()}] [FAIL] 删除失败 {rel_path(path, root)}  {exc}", "FAIL")

        self._log(
            f"[{now_ts()}] [INFO] 清理备份{'部分失败' if failed else '完成'}："
            f"已删除 {removed} 个，失败 {failed} 个",
            "FAIL" if failed else "INFO",
        )
        self.window.set_status(f"清理备份：已删除 {removed} 个，失败 {failed} 个")

        if failed:
            self.window.notify(
                "清理备份", f"已删除 {removed} 个，{failed} 个删除失败（可能被占用或只读）。", "warning"
            )
        else:
            self.window.notify("清理备份", f"已删除 {removed} 个 .orig 备份文件。", "info")

    # -------- 开始
    def on_start(self):
        if self.worker and self.worker.isRunning():
            return

        cfg = self.window.get_config()
        self.remember_dir(cfg["root"])

        error = validate_config(cfg)
        if error:
            self.window.notify("参数检查", error, "warning")
            return

        root = Path(cfg["root"])
        files, excluded_dirs = scan_files(root, cfg["extensions"], cfg["recursive"], cfg["excludes"])

        if not files:
            self.window.notify(
                "扫描结果",
                "没有找到可处理的文件。\n请检查代码目录、文件类型勾选和排除目录。",
                "warning",
            )
            return

        if not cfg["dry_run"]:
            summary = (
                f"将对 {len(files)} 个文件执行风格化。\n\n"
                f"目录：{root}\n"
                f"递归子目录：{'是' if cfg['recursive'] else '否'}\n"
                f"保留 .orig 备份：{'是' if cfg['backup'] else '否'}\n\n"
                "说明：只调整代码的缩进、空格与换行，不删除文件、不涉及硬盘格式化。\n\n"
                "是否继续？"
            )
            if not self.window.ask_confirm("确认风格化", summary):
                return

        self._close_logger()
        logger = LogFile()
        self.logger = logger
        self.job = cfg

        info = f"共找到 {len(files)} 个文件"
        if excluded_dirs:
            info += f"（跳过 {excluded_dirs} 个排除目录）"
        self._log(f"[{now_ts()}] [INFO] {info}", "INFO")
        self._log(f"[{now_ts()}] [INFO] 日志文件：{logger.path}", "INFO")
        if cfg["dry_run"]:
            self._log(f"[{now_ts()}] [INFO] 预览模式：只报告将会修改的文件，不改动任何文件", "INFO")

        job = dict(cfg)
        job["files"] = files
        job["root"] = root

        worker = FormatWorker(job)
        worker.log_signal.connect(lambda line, level: self._log(line, level))
        worker.progress_signal.connect(self.window.set_progress)
        worker.done_signal.connect(self.on_done)
        self.worker = worker

        self.window.set_progress(0, len(files))
        self.window.set_running(True)
        worker.start()

    # -------- 停止
    def on_stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self._log(f"[{now_ts()}] [INFO] 已请求停止，将在当前文件处理完成后中止", "INFO")

    # -------- 关闭窗口
    def on_close_requested(self):
        self.pending_close = True
        self.on_stop()

    # -------- 完成
    def on_done(self, stat: dict):
        worker = self.worker
        self.worker = None
        if worker:
            worker.wait(3000)

        done = stat["ok"] + stat["skip"] + stat["fail"]
        self.window.set_progress(done, stat["total"])
        self.window.set_running(False)

        head = "已停止" if stat["stopped"] else "完成"
        if stat["dry_run"]:
            detail = f"将会修改 {stat['ok']}，无需修改 {stat['skip']}，失败 {stat['fail']}"
            note = "。本次为预览模式，未实际修改文件。"
        else:
            detail = f"已格式化 {stat['ok']}，无变化 {stat['skip']}，失败 {stat['fail']}"
            note = ""
        line = (
            f"[{now_ts()}] [INFO] {head}：共 {stat['total']}，{detail}，"
            f"用时 {stat['elapsed']:.2f}s{note}"
        )
        self._log(line, "FAIL" if stat["fail"] and not stat["dry_run"] else "INFO")
        self.window.set_summary(stat)
        self._close_logger()

        if self.pending_close:
            self.pending_close = False
            self.window.close()
            return

        if stat["dry_run"]:
            self.window.notify(
                "预览完成",
                f"{stat['ok']} 个文件将会被修改，{stat['skip']} 个无需修改"
                + (f"，{stat['fail']} 个出错" if stat["fail"] else "")
                + "。\n原文件未被改动。",
                "info",
            )
        elif stat["fail"]:
            self.window.notify(
                "处理完成",
                f"有 {stat['fail']} 个文件处理失败，共处理 {stat['total']} 个文件。\n详见日志。",
                "warning",
                show_log_button=True,
            )

    # -------- 退出保护
    def shutdown(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(3000)
        self._close_logger()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AstyleTool")
    app.setOrganizationName("my_astyle")

    window = MainWindow()
    window.load_settings()
    controller = AppController(window)
    app.aboutToQuit.connect(controller.shutdown)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
