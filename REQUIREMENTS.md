# Astyle 批量风格化工具 — 需求说明书（定稿 v1.0，待确认）

- 日期：2026-10-25（界面栈变更见 10.10，2026-10-26）
- 状态：**已实现**。第 1–9 节为需求口径（已按 v2.1 的 tkinter 实现更新），第 10 节为逐版本变更记录。
- 形态：本机自用 Windows 桌面小工具，**tkinter（Python 标准库，无第三方依赖）**，共 2 个 Python 文件。

---

## 1. 背景与目标

现状：在 Source Insight 中对**单个文件**执行脚本

```
"D:\astyle\astyle.exe" --options="D:\astyle\.astylerc" %f
```

目标：做一个 GUI，把"单文件"扩展成"整目录批量"，**格式化效果与上面那条命令完全一致**（同一个 exe、同一份 `.astylerc`、不额外施加风格参数），并能逐文件看到处理结果。

---

## 2. 环境与实测结论（已在本机验证，重要）

| 项目 | 实测 |
|---|---|
| Python | 3.10.11 |
| GUI 库 | Python 内置 `tkinter`（Tk 8.6），**无需安装第三方包**；v2.1 起由 PyQt6 换成 tkinter |
| astyle | Artistic Style **3.6.16**，`D:\astyle\astyle.exe` |
| 配置文件 | `D:\astyle\.astylerc`，2805 字节 |

### 2.1 实测发现的 4 个关键事实（直接影响实现）

| # | 事实 | 影响 |
|---|---|---|
| R1 | `.astylerc` 里含有 `--quiet`（第 112 行），**astyle 对文件不输出任何文字**（实测加 `-v -Q` 也压不住 `--quiet`） | **不能靠解析 astyle 输出判断"已格式化/无变化"**。改用"格式化前后文件内容哈希对比"判定，100% 可靠 |
| R2 | `.astylerc` 里含有 `--suffix=none`，且实测命令行追加 `--suffix=.orig` **无效**（不会生成 .orig） | 备份功能**由程序自己实现**（复制一份 `<文件名>.orig`），与 astyle 参数解耦 |
| R3 | 单文件成功格式化的退出码为 `0`；本工具参数里**不需要** `--recursive`（逐文件调用） | 退出码非 0 即可判为失败，再叠加哈希判定区分"已改/未改" |
| R4 | `.astylerc` 还含 `--mode=c`、`--lineend=windows`、`--style=allman` 等全部风格项 | 程序**只追加** `--options=<rc>` 和 `--suffix=none`、`--dry-run` 至多这两个开关，保证风格与 Source Insight 完全一致 |

> 结论：判定逻辑与备份逻辑都必须由 Python 自己完成，不能依赖 astyle 的输出文本和 `--suffix`。

---

## 3. 已确认的决策（原 Q1–Q15）

| 编号 | 决策 |
|---|---|
| Q1 | 默认**递归**子目录，界面可取消 |
| Q2 | 默认**保留备份**（生成 `xxx.c.orig`），界面可取消 |
| Q3 | 扩展名可勾选：`.c .h .cpp .hpp`（v1.2 移除 `.cc/.cxx/.inl`），默认只勾 `.c` `.h` |
| Q4 | 提供**预览模式**（dry-run），只报告会改哪些文件，绝不写盘 |
| Q5 | 支持**排除目录**，多个用 `;` 分隔，也可用"添加"按钮选目录 |
| Q6 | 日志**同时写入文件** `logs\astyle_YYYYMMDD_HHMMSS.log` |
| Q7 | 有失败时**结束后弹窗汇总**提示"N 个文件处理失败" |
| Q8 | **串行**处理，不开多进程 |
| Q9 | 代码目录只选**一个**根目录（递归覆盖全部子目录） |
| Q10 | **不打包** exe，`python main.py` 直接跑 |
| Q11 | **两个文件**：`ui_main.py`（只放界面）+ `main.py`（入口与全部业务逻辑） |
| Q12 | 界面：纯中文 + **系统默认浅色**，简洁原生观感 |
| Q13 | 不提供"一键还原"，失败/误操作靠 `.orig` 手工回退 |
| Q14 | 界面参数追加在 `.astylerc` 之后；但**不做**任何会改变风格的覆盖参数 |
| Q15 | 不做按修改时间过滤 |
| 附加 | 采用**逐文件调用**方式（每文件一次 astyle），以获得精确到文件的日志与"停止"能力 |

---

## 4. 功能需求

### 4.1 窗口布局（默认 610×620，可拉伸，日志区占剩余空间）

```
┌──────────────────────────────────────────────────────────────────────┐
│ Astyle 批量格式化工具                                                 │
├──────────────────────────────────────────────────────────────────────┤
│ Astyle 程序  [ D:\astyle\astyle.exe              ] [浏览] [检测]      │
│ 风格配置     [ D:\astyle\.astylerc               ] [浏览] [查看]      │
│ 代码目录     [ D:\project\src                    ] [浏览]             │
├──────────────────────────────────────────────────────────────────────┤
│ 选项： ☑递归子目录  ☑保留 .orig 备份  ☐预览模式(不改文件)            │
│ 类型： ☑.c ☑.h ☐.cpp ☐.hpp                                            │
│ 排除目录 [build;output;third_party               ] [添加]             │
├──────────────────────────────────────────────────────────────────────┤
│ [开始风格化]  [停止]  [清空日志]  [打开日志目录] [清理.orig备份]       │
│ 进度 [██████████░░░░░░░░░░]  12 / 48                                  │
├──────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │[12:01:33] [INFO] 共扫描到 48 个文件（排除 2 个目录）              │ │
│ │[12:01:33] [OK  ] app_main.c                       已格式化  0.08s │ │
│ │[12:01:33] [SKIP] util.h                           无变化    0.05s │ │
│ │[12:01:34] [FAIL] broken.c                         退出码 1        │ │
│ │[12:01:34] [INFO] 完成：共 48，已格式化 12，无变化 35，失败 1，3.2s│ │
│ └──────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ 状态：完成   处理 48   已改 12   无变化 35   失败 1   用时 3.2s       │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 输入项与控件行为

| 控件 | 类型 | 行为 |
|---|---|---|
| Astyle 程序 | Entry + 浏览 + 检测 | 默认 `D:\astyle\astyle.exe`；浏览过滤 `*.exe`；**检测**按钮执行 `astyle --version`，把版本号显示在状态栏/日志（同时验证可执行性）；可手动输入/粘贴（tkinter 原生不支持拖放，v2.1 取消拖放） |
| 风格配置 | Entry + 浏览 + 查看 | 默认 `D:\astyle\.astylerc`；**查看**按钮弹出只读 `Toplevel` 显示 rc 全文（等宽字体 + 双向滚动条，可复制，不提供编辑保存）；同样只支持输入/粘贴 |
| 代码目录 | Entry + 浏览 + 历史 | 默认空；**历史**按钮下拉最近 10 个用过的目录（浏览、从历史切换、点开始都会记录）；路径存在性在点"开始"时统一校验，输入框不做实时变红 |
| 排除目录 | Entry + 添加 | 分号 `;` 分隔；"添加"打开目录选择框并把路径追加进去（已存在则不重复添加）；匹配规则：按目录名精确匹配（如 `build` 匹配任意层的 build 目录）或按绝对路径前缀匹配 |
| 开始风格化 | ttk.Button | 见 4.3 流程；运行中禁用（原文字"开始格式化"易被误解为硬盘格式化，v1.3 改为"开始风格化"） |
| 停止 | ttk.Button | 运行中才可用；**不杀进程**，处理完当前文件后停止，日志写"已请求停止，将在当前文件处理完成后中止" |
| 清空日志 | ttk.Button | 只清界面文本框，日志文件不受影响 |
| 打开日志目录 | ttk.Button | `os.startfile(logs目录)` |
| 清理.orig备份 | ttk.Button | 删除**代码目录**下所有 `*.orig`；递归范围跟随"递归子目录"勾选；先弹确认框（显示文件数与范围），再逐个删除并在日志记一行；删除失败（被占用/只读）逐条记 `FAIL`；运行中禁用 |

**持久化**：关闭窗口时用 `ui_main.Settings`（`configparser`，`interpolation=None`）写入 `程序目录\settings.ini` 的 `[General]` 段，键为 `exe / rc / root / recursive / backup / dry_run / exts / excludes / history / geometry`，UTF-8 明文；`geometry` 存 `winfo_geometry()`（如 `610x620+120+80`）。下次启动自动恢复。旧版 Qt 写下的带引号值、双写反斜杠在读取时做了兼容还原。

**快捷键**：`Ctrl+Enter` 开始，`Esc` 停止（可选，v2.1 未实现；如需可用 `bind("<Control-Return>")` / `bind("<Escape>")`）。

### 4.3 执行流程

```
[开始] → 校验 → 扫描文件 → 确认 → 逐文件处理 → 汇总 → 收尾
```

1. **校验**（任一失败则由 `messagebox.showwarning/showerror` 提示并中止，不进入扫描）
   - exe 路径非空且文件存在（建议同时校验扩展名 .exe）
   - rc 路径非空且文件存在
   - 代码目录非空且是已存在目录
   - 至少勾选一种扩展名
2. **扫描**（同线程内快速完成，>2000 文件也够快）
   - 递归开关决定是否 `rglob`；按勾选扩展名过滤；跳过 `*.orig`、`*.bak` 自身
   - 跳过"排除目录"命中的整棵子树
   - 结果按路径字符串升序排列，保证日志顺序稳定
   - 扫描到 0 个文件 → 提示"没有找到可处理的文件"，中止
3. **确认**（仅实际模式，非预览）
   - 弹一个确认框：标题 `确认风格化`，正文 `将对 48 个文件执行风格化。… 说明：只调整代码的缩进、空格与换行，不删除文件、不涉及硬盘格式化。`（预览模式不弹，直接跑）
4. **逐文件处理**（后台 `threading.Thread`（daemon）+ `queue.Queue` 事件，串行；主线程 `after(60ms)` 轮询取事件）
   - **预览模式**：把文件复制到 `%TEMP%\astyle_preview_<随机>\`，对副本执行 astyle，比较复制前后副本内容哈希 → 输出 `将会修改` / `无需修改`，结束后删除临时目录。**原件字节零改动**。
   - **实际模式**：
     a. 若勾选备份 → 复制 `<file>` 为 `<file>.orig`（已存在则直接覆盖，`.orig` 始终等于本次格式化前的内容）
     b. 读入原文件字节 → `sha256`
     c. `subprocess.run([exe, "--options=" + rc, file], shell=False, capture_output=True)`
     d. 再读字节 → `sha256`；两次不同 → `OK/已格式化`；相同 → `SKIP/无变化`
     e. 退出码非 0 → `FAIL`，附输出片段（若被 `--quiet` 抑制则记"退出码 N"）
   - 每处理完一个文件立刻发信号刷新一行日志与进度
   - 每 1 个文件检查一次中断标志
5. **汇总**：状态栏 + 日志末行 `完成：共 N，已格式化 A，无变化 B，失败 C，用时 T s`
   - 实际模式且 C>0 → 弹窗 `有 C 个文件处理失败，共处理 N 个文件。详见日志。`（tk 版为普通 `messagebox.showwarning`，不再附带"打开日志目录"按钮，需要时用主界面的同名按钮）
   - 预览模式 → 弹窗 `A 个文件将会被修改，B 个无需修改。原文件未被改动。`（不执行任何写操作）
6. **收尾**：恢复按钮可用状态；`self.worker = None`；日志文件句柄关闭。

### 4.4 日志规范

- 界面：`tk.Text`（`state="disabled"` 只读、`wrap="none"`、`Consolas 10pt`、双向滚动条），插入后 `see("end")` 自动滚动到底，支持选中复制。
- 单行格式：`[HH:MM:SS] [STATUS] <相对路径>  <说明>  <耗时s>`
  - 路径显示**相对代码目录**的路径，避免超长（tk 版不提供 tooltip 绝对路径）。
  - STATUS 与配色：`OK` 绿、`SKIP` 灰、`FAIL` 红、`INFO` 默认色；实现上用 `Text.tag_configure(<level>, foreground=...)` 预定义 4 个标签，插入行时带对应标签（`log_edit.insert("end", line, tag)`）。
- 日志文件：`<程序所在目录>\logs\astyle_YYYYMMDD_HHMMSS.log`，**UTF-8 带 BOM**（Windows 记事本友好），内容与界面完全一致（纯文本，无颜色）。目录不存在时自动创建。
- 失败行同时写 astyle 的 stderr/stdout 原文（若为空则写退出码）。

### 4.5 异常与边界处理

| 场景 | 处理 |
|---|---|
| astyle 路径不存在 / 不是 exe | 开始前弹窗拦截；"检测"按钮也提示 |
| rc 路径不存在 | 弹窗拦截（但允许"仅用默认风格继续"？**不提供**，避免和 SI 效果不一致） |
| 目录无权限 / 文件被占用（返回非 0） | 记 FAIL 继续，不中断整批 |
| 文件是只读属性 | astyle 会报错 → FAIL，日志提示"可能是只读文件" |
| 路径含中文/空格/`&` | 全程 `subprocess` 参数列表 + `Path`，禁用 shell 拼接；已覆盖 |
| astyle 卡死 | 单文件超时 60s（`subprocess.run(timeout=60)`），超时 → FAIL("超时") |
| 用户在运行中关闭窗口 | `protocol("WM_DELETE_WINDOW", on_close_requested)` 弹确认：`文件正在处理中，确定中止并退出吗？` → 置中断标志，等当前文件结束再退出（`_shutdown` 中 `join(3.0)`） |
| 运行中重复点开始 | 按钮已禁用，不会重入 |
| `.orig` 已存在 | 直接覆盖为本次格式化前的内容；若本次格式化无变化，则删除该 `.orig` |

---

## 5. 文件与模块划分（Q11：两个文件）

### 5.1 `ui_main.py` —— 只负责界面（不含任何 astyle / subprocess 逻辑）

```
class Settings:                       # settings.ini 读写（configparser，[General] 段）
class PlaceholderEntry(tk.Entry):     # 带灰色占位提示的输入框（tk 无内建 placeholder）
def read_text_any(path) -> str        # utf-8-sig 优先，回退 gbk

class MainWindow(tk.Tk):
    # 界面原语（供 main.py 调用，本身不绑命令）
    def exe_path() / rc_path() / code_dir() -> str
    def set_code_dir(path)
    def get_config(self) -> dict      # 采集界面所有输入 → 配置字典
    def pick_exe() / pick_rc() / pick_code_dir() / pick_exclude_dir() -> str
    def append_exclude(path)
    def append_log(text, level="INFO")   # level: OK/SKIP/FAIL/INFO
    def clear_log()
    def set_progress(done, total) / set_running(running)
    def set_status(text) / set_summary(stat)
    def notify(title, text, level="info")   # 封装 messagebox
    def ask_confirm(title, text) -> bool
    def open_log_dir()
    def save_settings() / load_settings()
```

- 负责：控件创建与布局（`ttk.LabelFrame` + `grid`）、`ttk.Style` 主题微调、占位提示、文件/目录选择框、日志着色标签、消息框封装、`settings.ini` 读写。
- **不负责**：进程调用、文件扫描、哈希比较、日志落盘、按钮命令绑定——**本文件不出现任何 `command=`/`protocol()` 绑定**，全部由 `main.py` 的 `AppController._connect_signals()` 注册。
- 控件本身以 `self.btn_xxx` / `xxx_edit` / `xxx_var` 形式公开，业务层直接 `configure(command=...)`。

### 5.2 `main.py` —— 入口 + 全部逻辑

```
def build_argv(exe, rc, target) -> list[str]
def run_astyle(exe, rc, target, timeout=60) -> tuple[int, str]
def sha256_file(p) -> str
def decode_output(b) -> str            # utf-8 优先，失败回退 gbk
def orig_path(p) -> Path
def backup_file(p) -> tuple[str, str]  # (OK/FAIL, 说明)
def scan_files(root, extensions, recursive, excludes) -> list[Path]
def scan_orig_files(root, recursive) -> list[Path]
def validate_config(cfg) -> str | None # 返回错误文本，None 表示通过

class FormatWorker:                    # threading.Thread(daemon) 封装，串行处理
    def __init__(job: dict, events: queue.Queue)
    def start() / request_stop() / is_running() / join(timeout)
    def run()                          # 投递 ("log", 行, 级别)/("progress", done, total)/("done", stat)

class LogFile:                         # 写 logs\astyle_YYYYMMDD_HHMMSS.log（UTF-8 BOM）
class AppController:                   # 业务控制器，_connect_signals() 是唯一的命令注册点
    def _pump()                        # after(60ms) 轮询 events 队列
    def on_pick_exe/on_pick_rc/on_view_rc/on_pick_code_dir/on_add_exclude
    def on_show_history/on_history_chosen/on_clear_history
    def on_check/on_start/on_stop/on_clean_orig/on_close_requested/on_done
def main()                             # MainWindow + load_settings + AppController + mainloop
```

- 负责：校验、扫描、备份、哈希判定、进程调用、超时、停止、日志落盘、汇总统计、弹窗触发（调用 UI 的 notify）。
- **不直接操作 tk 控件之外的状态**：读写界面一律走 `MainWindow` 的公开方法与 `configure()`；后台线程只往队列投事件，绝不碰控件（tk 只允许主线程更新界面）。

### 5.3 目录结构

```
d:\Study\python\sy_astyle\
├── main.py            # 入口 + 全部业务逻辑（FormatWorker / AppController）
├── ui_main.py         # 界面层（tkinter：控件、界面原语、日志、弹窗、settings.ini）
├── settings.ini       # 界面配置（关闭窗口时写入，UTF-8 明文）
├── REQUIREMENTS.md    # 本需求文档（保留）
└── logs\              # 运行时自动生成
```

---

## 6. 技术方案要点

| 关注点 | 方案 |
|---|---|
| 进程调用 | `subprocess.run(argv_list, shell=False, capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)` |
| 命令行构造 | `[exe, f"--options={rc}"]` + 预览时 `+["--dry-run"]` + `[file]`；**不加**风格类参数 |
| 异步 | `threading.Thread`（daemon）跑 `FormatWorker`，只往 `queue.Queue` 投事件；主线程 `after(60ms)` 轮询刷新界面；停止用 `threading.Event` 协作式中止 |
| 编码 | 捕获 bytes → 先 `utf-8` 再 `gbk` 回退（中文 Windows 报错常为 GBK） |
| 结果判定 | 前后 `sha256` 对比（见 R1），失败看退出码 |
| 备份 | Python `shutil.copy2` 生成 `.orig`（见 R2） |
| 预览 | 复制到临时目录实际格式化后对比（见 R1：astyle 输出被 quiet 抑制、dry-run 退出码不可靠） |
| 设置持久化 | `configparser`（`interpolation=None`）读写 `settings.ini` 的 `[General]` 段，与 `main.py` 同目录，UTF-8 明文（旧版 Qt 写下的引号/双反斜杠在读取时兼容还原） |
| 单实例 | 不做，允许多开（风险低，自用） |
| 日志性能 | 每行 `Text.insert("end", line, tag)` + `see("end")` 一次，插入时临时 `state="normal"`、写完复位 `disabled`；文件句柄常开 `flush()` |

---

## 7. 明确不做（本次范围外）

- 不做风格规则编辑器（`.astylerc` 只读查看，编辑仍在外部）。
- 不做 Source Insight 集成/插件。
- 不做格式化前后 diff 预览。
- 不做多目录批量、不做多进程并发、不做按 mtime 过滤。
- 不做"一键还原 .orig"。
- 不打包 exe（后续想加再说）。
- 不做深色主题/皮肤。

---

## 8. 验收标准

1. `python main.py` 能启动，窗口 3 秒内出现，无异常输出。
2. 首次启动三个路径框已填好 `D:\astyle\astyle.exe`、`D:\astyle\.astylerc`、空目录。
3. 选一个含 10 个以上 `.c/.h` 且有子目录的工程目录，点"开始"：
   - 每个文件日志一行，状态正确（未格式化的显示 `OK`，已格式化的显示 `SKIP`）
   - 勾选备份时生成 `xxx.c.orig`，且内容与格式化前一致
   - 处理后的文件用 git diff 检查，改动与 Source Insight 单文件执行结果**逐字节一致**
4. 勾选"预览模式"：所有文件 mtime 与内容零变化；日志给出"将会修改 / 无需修改"；结束后临时目录被清理。
5. 处理 500 个文件期间可拖动窗口、可点"停止"（2 秒内停下），界面不"未响应"。
6. 中文路径（如 `D:\工程\代码`）下正常处理，日志与窗口中文不乱码。
7. 关闭再打开，路径、勾选项、排除列表全部恢复。
8. `logs\` 下生成当次日志文件，用记事本打开中文正常。
9. 把 `.c` 文件设为只读后处理，该文件显示 `FAIL`、其余文件继续处理，结束后弹窗汇总失败数。

---

## 9. 交付与下一步

- 交付：`ui_main.py`（约 510 行）+ `main.py`（约 810 行），保持注释适度、**无第三方依赖**（只用 Python 标准库：`tkinter` / `queue` / `threading` / `configparser` / `subprocess`）。
- 编码完成后按第 8 节验收项实测（预览模式优先，避免误改文件），再交付确认。

---

## 10. 实现备注（v1.0 已完成，2026-10-25）

> 10.4–10.8 记录的是 PyQt6/Qt Designer 时期的实现。v2.1 起界面已改为 tkinter（见 10.10），这几节仅作历史保留，与当前代码不再对应。

### 10.1 与需求的 3 处实现差异（已实测验证）

| 项 | 文档原文 | 实际实现 | 原因 |
|---|---|---|---|
| 预览模式 | 追加 `--dry-run` | **不加** `--dry-run`：把文件复制到临时目录，对副本真实格式化后比较哈希 | `--quiet` 让 astyle 无输出，`--dry-run` 退出码也不可靠；实测副本方案能准确报出"将会修改/无需修改"且原文件零改动 |
| 清空日志 | 走 `clear_requested` 信号 | 界面内部直接处理 | 纯 UI 动作，无需经过业务层 |
| 命令行参数 | `--options` + 至多 `--suffix=none`/`--dry-run` | 固定 `--options=<rc>` + `--suffix=none` + 目标文件 | 备份由程序自己做，避免 astyle 再生成一份 `.orig`；只影响备份，不影响风格 |

### 10.2 实测验证结果

| 验证项 | 结果 |
|---|---|
| 扫描/递归/排除目录 | 通过（`build` 目录被跳过，计数正确） |
| 实际格式化 + 哈希判定 | 通过（未格式化→`OK`，已格式化→`SKIP`） |
| `.orig` 备份 | 通过（内容与格式化前逐字节一致；已有旧备份被覆盖） |
| 预览模式 | 通过（原文件零改动；未格式化目录报"将会修改"，已格式化目录报"无需修改"） |
| 只读文件 | 通过（`FAIL` + astyle 原始报错，中文正常显示，其余文件继续） |
| 中文/空格路径 | 通过（`...\工程 代码\` 正常处理） |
| 日志落盘 | 通过（`logs\astyle_YYYYMMDD_HHMMSS.log`，UTF-8 BOM，记事本可读） |
| 设置持久化 | 通过（路径、勾选项、扩展名、排除列表往返一致） |
| 界面创建/渲染 | 通过（截图检查布局无重叠） |

### 10.3 v1.1 追加：清理 .orig 备份按钮（2026-10-25）

- 位置：操作按钮行，"打开日志目录"之后，按钮文字 `清理.orig备份`。
- 依赖输入：**代码目录**（未填 → 提示"请先指定代码目录"）、**递归子目录**勾选（决定只清当前层还是含全部子目录）。
- 流程：收集 `*.orig` → 无命中则提示"该目录下没有 .orig 备份文件" → 弹确认框（显示数量与范围）→ 逐个 `unlink` → 日志逐条记录 + 末行汇总 → 失败时弹窗提示"可能被占用或只读"。
- 安全点：删除的是 `*.orig` 备份，**不会动源码文件**；运行格式化任务期间按钮禁用，避免与后台处理交叉。
- 实测：递归删除 3 个（含子目录）、非递归只删当前层、重复清理提示无文件、空目录提示、未填目录提示、按钮随运行状态启禁 —— 全部通过。

### 10.4 v1.4 追加：PyQt5 → PyQt6 迁移（2026-10-25）

运行环境：PyQt6 6.4.2 / Qt 6.4.2（Python 3.10.11）。功能与界面布局不变，仅做 API 适配：

| 类别 | PyQt5 写法 | PyQt6 写法 |
|---|---|---|
| 模块导入 | `PyQt5.QtCore/QtGui/QtWidgets` | `PyQt6.QtCore/QtGui/QtWidgets` |
| 事件循环/对话框 | `app.exec_()`、`dlg.exec_()` | `app.exec()`、`dlg.exec()`（`exec_` 已移除） |
| 作用域枚举 | `Qt.AlignRight`、`Qt.TextSelectableByMouse` | `Qt.AlignmentFlag.AlignRight`、`Qt.TextInteractionFlag.TextSelectableByMouse` |
| 文本换行 | `QPlainTextEdit.NoWrap` | `QPlainTextEdit.LineWrapMode.NoWrap` |
| 光标定位 | `QTextCursor.End` | `QTextCursor.MoveOperation.End` |
| 消息框 | `QMessageBox.Information / Question / ActionRole / AcceptRole / YesRole / NoRole` | `QMessageBox.Icon.* / QMessageBox.ButtonRole.*` |
| sip 警告屏蔽 | `warnings.filterwarnings("ignore", message=r"sipPyTypeDict\(\) is deprecated.*")` | **已删除**（PyQt6 不再产生该警告） |

其他说明：

- `pyqtSignal` 在 PyQt6 中仍可用，信号定义无需改动。
- 高 DPI 缩放：Qt6 默认启用，无需设置 `AA_EnableHighDpiScaling` 等已废弃属性。
- 实测：离屏（`QT_QPA_PLATFORM=offscreen`）下窗口创建、`load_settings/save_settings`、`append_log`、`set_progress` 全流程正常，无异常输出。

### 10.5 v1.5 追加：配置改存 settings.ini（2026-10-25）

- 位置：`ui_main.py` 的 `SETTINGS_FILE = <程序目录>/settings.ini`，`QSettings(path, QSettings.Format.IniFormat)`。
- 格式：UTF-8 明文（Qt6 已移除 `setIniCodec`，中文路径直接明文写入，不再有 Qt5 的 `%XX` 转义）；含 `,` `;` 的值自动加引号，`geometry` 存为 `@ByteArray(...)`，均可正常往返。
- 迁移：`open_settings()` 在 `settings.ini` 不存在时，读取旧注册表项 `HKCU\Software\my_astyle\AstyleTool` 并整体写入 ini（只读不删原值），保证升级后不丢路径与勾选项。
- 写入时机不变：仍只在 `closeEvent` → `save_settings()` → `sync()`。
- 注意：`QSettings(org, app, format)` 重载在 PyQt6 中已移除，读旧注册表须用 `QSettings(Format.NativeFormat, Scope.UserScope, org, app)`。
- 实测：读取既有 ini、修改后 `save_settings()` 落盘、重建窗口再 `load_settings()`，中文路径 `D:\工程 代码\src`、勾选项、排除目录 `build;out` 往返一致。

### 10.6 v1.6 追加：界面改用 Qt Designer 的 .ui（2026-10-25）

- 结构：`main_window.ui`（布局唯一来源）→ `pyuic6 -o ui_main_window.py main_window.ui` → `ui_main.py` 中 `class MainWindow(QMainWindow, Ui_MainWindow)`，`__init__` 调 `setupUi(self)`。取代原 Q11 的"两个文件"约定。
- `ui_main.py` 只保留 .ui 表达不了的部分：`PathLineEdit` 拖放类、`_mode` 赋值、扩展名复选框映射、日志配色、`notify/ask_confirm`、`.astylerc` 只读对话框、`settings.ini` 读写、历史目录菜单。
- 提升部件：`PathLineEdit` 原在 `ui_main.py`，会导致 `ui_main_window.py` 末尾 `from ui_main import PathLineEdit` 与其反向导入形成循环。v1.8 已拆到 `path_line_edit.py`，.ui 的 Header file 同步改为 `path_line_edit`，依赖变为单向：`path_line_edit ← ui_main_window ← ui_main ← main`。
- 扩展名复选框：.ui 中固定为 `chk_ext_c/h/cpp/hpp` 四个控件，代码用 `EXT_CHECKBOXES` 字典映射为 `self.ext_boxes`；在 Designer 里增删文件类型需同步改该字典与 `ALL_EXTS`。
- 新增功能：路径行"历史"按钮（`btn_history`，QToolButton），下拉最近 10 个使用过的代码目录。记录时机：浏览选目录、从历史中切换、点"开始风格化"。存储在 `settings.ini` 的 `history` 键（JSON 数组，UTF-8 明文），菜单展示时过滤已不存在的目录。
- 修复 .ui 中的设计错误：进度条 `minimum/maximum/value` 原为 `-2/3/-2`，改为 `0/1/0`（运行期仍由 `set_progress()` 接管范围）。
- 实测：控件加载、扩展名映射、历史目录去重/排序/持久化、"历史"菜单弹出、开始信号携带配置、预览与实际两种流程均正常。

### 10.7 v1.7 追加：信号槽全部集中到 main.py（2026-10-25）

- 分工：`main_window.ui` 只放布局；`ui_main_window.py` 只放生成代码；`ui_main.py` 只放控件细化与界面原语（**不含任何 `.connect(...)`**）；`main.py` 的 `AppController._connect_signals()` 是唯一的信号槽入口（共 20 处连接）。
- `ui_main.MainWindow` 只保留一个信号 `close_requested`：因为 `closeEvent` 是 Qt 事件、无法搬到业务层，等价于"视图 → 业务"的通知。
- 原 `start_requested/stop_requested/check_requested/clean_orig_requested` 已删除，改为业务层直接连接控件：`btn_start.clicked → on_start()`、`btn_check.clicked → on_check()` 等；槽函数内部统一用 `window.get_config()/exe_path()/code_dir()` 取输入，不直接读控件。
- 界面原语（供业务层调用，本身不连信号）：`pick_exe()`、`pick_rc()`、`pick_code_dir()`、`pick_exclude_dir()`、`append_exclude()`、`set_code_dir()`、`code_dir()`、`exe_path()`、`rc_path()`、`get_config()`、`append_log()`、`clear_log()`、`set_progress()`、`set_running()`、`set_status()`、`set_summary()`、`notify()`、`ask_confirm()`、`open_log_dir()`、`save_settings()`、`load_settings()`。
- `.astylerc` 只读查看窗口由 `AppController.on_view_rc()` 构造（含"关闭"按钮的连接），`ui_main.show_astylerc()` 已移除。
- 历史目录：`remember_dir()/history()/save_history()/refresh_history_menu()/on_history_chosen()/on_clear_history()` 全部在 `AppController`；`QToolButton` 在 `ui_main` 中设为 `InstantPopup`，菜单对象由业务层 `setMenu()` 装入，菜单在 `aboutToShow` 时重建（避免在菜单自身槽里清空 action）。
- 实测：点"检测"→状态栏出现 `Artistic Style Version 3.6.16`；点"查看"→对话框拿到 `.astylerc` 全文；"清空日志"生效；"清理.orig备份"无目录时正确提示；"历史"下拉列出目录并可切换、切换后记忆顺序正确；开始按钮走完整预览流程。

### 10.8 v1.8 追加：.ui 尺寸微调（2026-10-25）

- 窗口：geometry 900×700、最小 880×620（原 600×700 与内容最小宽冲突，运行期被动撑开）。
- 去掉 3 个 GroupBox（选项 / 操作 / 进度）写死的 `minimumSize` 宽 570，改由内容决定。
- 去掉 3 个路径框（320）与排除目录框（390）的最小宽，宽度交给布局自动分配。
- `progress_label`：最小宽 56→80，对齐 Center→`AlignRight|AlignVCenter`，避免数字位数变化时宽度跳动。
- `btn_history`：补 toolTip「选择历史代码目录（最近 10 个）」。
- 第 6 条已完成：`PathLineEdit` 迁到 `path_line_edit.py`，.ui 提升头文件改为 `path_line_edit`，`ui_main.py` 的 `from ui_main_window import Ui_MainWindow` 回到文件顶部，不再依赖导入顺序。
- 窗口改为 610×620（原 900×700）；随后把进度条最小宽 480→380，使内容最小宽从 604 降到 524，610 宽下留 86px 余量，避免高 DPI / 大字号时被内容反向撑宽。
- 注意：`.ui` 的 `resize()` 只在构造时生效，`load_settings()` 的 `restoreGeometry()` 会覆盖它；改默认窗口尺寸后需删掉 `settings.ini` 的 `geometry` 行，否则旧尺寸继续生效。

### 10.9 v1.9 追加：无变化文件不再保留 .orig（2026-10-26）

- 规则：勾选"保留 .orig 备份"时，只有**实际发生修改**的文件才留下 `.orig`；格式化前后哈希相同（`SKIP/无变化`）时，把刚生成的备份删掉，避免目录里堆积一堆与源文件完全相同的备份。
- 备份语义（v2.0 简化）：`backup_file()` 每次直接覆盖旧 `.orig`，`.orig` 恒等于"本次格式化前的内容"，因此无需判断备份来源，也不再有 `已存在旧备份，跳过备份` 这条 INFO。
- 日志：无变化且删除成功记 `无变化（已删除备份）`；删除失败（被占用/只读）记 `无变化（备份删除失败：原因）`，仍按 `SKIP` 计数。
- 实现：`orig_path()` 抽出 `<文件名>.orig` 路径；`FormatWorker._process_one()` 用 `backed_up` 标记本次是否做了备份，无变化时据此删除。
- 实测：a.c 有变化且已有旧 `.orig`→被覆盖为本次格式化前内容；b.c 无变化且已有旧 `.orig`→该 `.orig` 被删除；c.c 无变化且原本无 `.orig`→不产生新文件。

### 10.10 v2.1 变更：界面栈由 PyQt6 换成 tkinter（2026-10-26）

- 结果：**彻底移除 PyQt6 依赖**，只用 Python 标准库，`python main.py` 直接可跑，无需 pip 安装任何包；功能与交互保持不变。
- 删除文件：`main_window.ui`（Designer 布局）、`ui_main_window.py`（pyuic6 生成物）、`path_line_edit.py`（提升部件拖放类），三者随本次重写一并移除。
- `ui_main.py`（`class MainWindow(tk.Tk)`）：
  - 布局：`ttk.LabelFrame`（路径设置 / 选项 / 操作 / 进度）+ `grid`，日志区占剩余空间；窗口默认 `610x620`，最小同值；`ttk.Style` 做浅色主题微调。
  - 输入框：`PlaceholderEntry(tk.Entry)` 提供灰字占位提示（tk 无内建 placeholder），`<FocusIn>/<FocusOut>` 显隐提示。
  - 设置：`Settings`（`configparser`）取代 `QSettings`，键名与旧版保持一致，读取时兼容旧 Qt 的引号值与双写反斜杠。
  - 日志：`tk.Text`（`state="disabled"`、`wrap="none"`）取代 `QPlainTextEdit`，`tag_configure` 取代 `QTextCharFormat` 逐行着色。
  - 弹窗：`notify/ask_confirm` 封装 `messagebox.showinfo/showwarning/showerror/askyesno`；`show_log_button` 参数保留但 tk 版不提供额外按钮。
  - `.astylerc` 只读查看：`tk.Toplevel` + 只读 `Text` + 双向滚动条（`main.AppController._show_text_dialog`）。
- `main.py`：
  - 后台：`FormatWorker` 改为 `threading.Thread`（daemon）封装，只往 `queue.Queue` 投 `("log", 行, 级别)` / `("progress", done, total)` / `("done", stat)`；主线程 `AppController._pump()` 用 `after(60ms)` 轮询消费（tk 控件只能主线程更新）。
  - 停止：`QThread.requestInterruption()` → `threading.Event`，仍为"当前文件处理完再停"。
  - 绑定：没有 `pyqtSignal`，`_connect_signals()` 用 `widget.configure(command=...)` 注册按钮命令，用 `window.protocol("WM_DELETE_WINDOW", ...)` 替代 `closeEvent`。
- 拖放取消：tkinter 原生不支持控件级文件拖放（需第三方 `tkinterdnd2`），本次移除三个路径框的拖放，改为输入/粘贴 + 浏览按钮。若后续仍要拖放，需重新引入第三方依赖。
- 未变部分：扫描/排除目录、备份与 `.orig` 语义、哈希判定、预览副本方案、日志落盘（UTF-8 BOM）、历史目录（`settings.ini` 的 `history` 键）、超时 60s、第 8 节验收项全部继续适用。

