# Astyle 批量风格化工具 — 功能说明

- 状态：**已实现**。本文档描述当前代码（`main.py` + `ui_main.py`）的实际功能。
- 形态：本机自用 Windows 桌面小工具，**tkinter（Python 标准库，无第三方依赖）**，共 2 个 Python 文件，`python main.py` 直接运行。

---

## 1. 背景与目标

现状：在 Source Insight 中对**单个文件**执行脚本

```
"D:\astyle\astyle.exe" --options="D:\astyle\.astylerc" %f
```

目标：做一个 GUI，把"单文件"扩展成"整目录批量"，**格式化效果与上面那条命令完全一致**（同一个 exe、同一份 `.astylerc`、不额外施加风格参数），并能逐文件看到处理结果。

---

## 2. 运行环境

| 项目 | 说明 |
|---|---|
| Python | 3.10.11 |
| GUI 库 | Python 内置 `tkinter`（Tk 8.6），**无需安装第三方包** |
| astyle | Artistic Style 3.6.16，`D:\astyle\astyle.exe` |
| 配置文件 | `D:\astyle\.astylerc` |

### 2.1 实测发现的 2 个关键事实（直接影响实现）

| # | 事实 | 影响 |
|---|---|---|
| R1 | `.astylerc` 里含有 `--quiet`，astyle 对文件**不输出任何文字**（实测加 `-v -Q` 也压不住） | 不能靠解析 astyle 输出判断"已格式化/无变化"，改用**格式化前后文件内容 sha256 对比**判定，100% 可靠 |
| R2 | `.astylerc` 里含有 `--suffix=none`，且实测命令行追加 `--suffix=.orig` 无效 | 备份功能由程序自己实现（`shutil.copy2` 复制一份 `<文件名>.orig`），与 astyle 参数解耦 |

> 结论：判定逻辑与备份逻辑都由 Python 自己完成，不依赖 astyle 的输出文本和 `--suffix`。

---

## 3. 设计决策

| 编号 | 决策 |
|---|---|
| D1 | 默认**递归**子目录，界面可取消 |
| D2 | 默认**保留备份**（仅对实际被修改的文件生成 `xxx.c.orig`），界面可取消 |
| D3 | 扩展名可勾选：`.c .h .cpp .hpp`，默认只勾 `.c` `.h` |
| D4 | 提供**预览模式**，只报告会改哪些文件，绝不写盘 |
| D5 | 支持**排除目录**，多个用 `;` 分隔，也可用"添加"按钮选目录 |
| D6 | 日志**同时写入文件** `logs\astyle_YYYYMMDD_HHMMSS.log` |
| D7 | 有失败时**结束后弹窗汇总**提示"N 个文件处理失败" |
| D8 | **串行**处理，不开多进程 |
| D9 | 代码目录只选**一个**根目录（递归覆盖全部子目录） |
| D10 | 不打包 exe，`python main.py` 直接跑 |
| D11 | **两个文件**：`ui_main.py`（只放界面）+ `main.py`（入口与全部业务逻辑） |
| D12 | 界面：纯中文 + 系统默认浅色，简洁原生观感 |
| D13 | 不提供"一键还原"，失败/误操作靠 `.orig` 手工回退 |
| D14 | **逐文件调用** astyle（每文件一次），以获得精确到文件的日志与"停止"能力 |
| D15 | 不做按修改时间过滤、不做风格参数覆盖 |

---

## 4. 功能说明

### 4.1 窗口布局（默认 610×620，可拉伸，日志区占剩余空间）

```
┌──────────────────────────────────────────────────────────────────────┐
│ 思远Astyle代码风格化工具 V0.1                                         │
├──────────────────────────────────────────────────────────────────────┤
│ 路径设置                                                              │
│  Astyle 程序  [ D:\astyle\astyle.exe            ] [浏览] [检测]       │
│  风格配置     [ D:\astyle\.astylerc             ] [浏览] [查看]       │
│  代码目录     [ D:\project\src                  ] [浏览] [历史]       │
├──────────────────────────────────────────────────────────────────────┤
│ 选项                                                                  │
│  ☑递归子目录  ☑保留 .orig 备份  ☐预览模式（不改文件）                │
│  文件类型： ☑.c ☑.h ☐.cpp ☐.hpp                                      │
│  排除目录 [build;output;third_party             ] [添加]              │
├──────────────────────────────────────────────────────────────────────┤
│ 操作                                                                  │
│  [开始风格化] [停止] [清空日志] [打开日志目录] [清理.orig备份]        │
├──────────────────────────────────────────────────────────────────────┤
│ 进度 [██████████░░░░░░░░░░]  12 / 48                                 │
├──────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │[12:01:33] [INFO] 共找到 48 个文件（跳过 2 个排除目录）            │ │
│ │[12:01:33] [OK  ] app_main.c                       已格式化  0.08s │ │
│ │[12:01:33] [SKIP] util.h                       无变化（已删除备份） │ │
│ │[12:01:34] [FAIL] broken.c                      退出码 1  …         │ │
│ │[12:01:34] [INFO] 完成：共 48，已格式化 12，无变化 35，失败 1，3.2s │ │
│ └──────────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ 状态：完成   处理 48   已改 12   无变化 35   失败 1   用时 3.2s       │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 输入项与控件行为

| 控件 | 类型 | 行为 |
|---|---|---|
| Astyle 程序 | Entry + 浏览 + 检测 | 默认 `D:\astyle\astyle.exe`；浏览过滤 `*.exe`；**检测**按钮执行 `astyle --version`（超时 15s），成功把版本号写入状态栏和日志，失败弹窗；支持手动输入/粘贴（不支持拖放） |
| 风格配置 | Entry + 浏览 + 查看 | 默认 `D:\astyle\.astylerc`；**查看**按钮弹出只读 `Toplevel` 显示 rc 全文（Consolas 等宽字体 + 双向滚动条，可选中复制，不提供编辑保存） |
| 代码目录 | Entry + 浏览 + 历史 | 默认空；**历史**按钮在按钮下方弹出菜单，列出最近 10 个用过的目录（浏览、从历史切换、点开始都会记录；菜单末项为"清除历史记录"）；路径存在性在点"开始"时统一校验，输入框不做实时变红 |
| 排除目录 | Entry + 添加 | 分号 `;` 分隔；"添加"打开目录选择框并把路径追加进去（已存在则不重复添加；若该目录位于代码目录内则存相对路径）。匹配规则：纯名字按**目录名精确匹配**（如 `build` 匹配任意层的 build 目录，不区分大小写）；含路径分隔符或绝对路径的项按**路径前缀匹配**（相对路径相对代码目录解析） |
| 开始风格化 | ttk.Button | 见 4.3 流程；运行中禁用 |
| 停止 | ttk.Button | 运行中才可用；**不杀进程**，处理完当前文件后停止，日志写"已请求停止，将在当前文件处理完成后中止" |
| 清空日志 | ttk.Button | 只清界面文本框，日志文件不受影响 |
| 打开日志目录 | ttk.Button | `os.startfile(logs目录)`（目录不存在时自动创建） |
| 清理.orig备份 | ttk.Button | 删除**代码目录**下所有 `*.orig`；递归范围跟随"递归子目录"勾选；先弹确认框（显示数量与范围），再逐个删除并在日志记一行；删除失败（被占用/只读）逐条记 `FAIL`；运行中禁用 |

三个输入框均为带灰色占位提示的 `PlaceholderEntry`（获得焦点时隐藏提示，失去焦点且为空时恢复）。

**持久化**：关闭窗口时用 `ui_main.Settings`（`configparser`，`interpolation=None`）写入 `程序目录\settings.ini` 的 `[General]` 段，键为 `exe / rc / root / recursive / backup / dry_run / exts / excludes / history / geometry`，UTF-8 明文；`geometry` 存 `winfo_geometry()`（如 `610x620+120+80`）。下次启动自动恢复（`geometry` 按正则校验后再应用）。

**快捷键**：不提供。

### 4.3 执行流程

```
[开始] → 校验 → 扫描文件 → 确认 → 逐文件处理 → 汇总 → 收尾
```

1. **校验**（任一失败则弹窗提示并中止，不进入扫描）
   - exe 路径非空且文件存在
   - rc 路径非空且文件存在
   - 代码目录非空且是已存在目录
   - 至少勾选一种扩展名
2. **扫描**（同线程内快速完成，>2000 文件也够快）
   - 递归开关决定是否遍历子目录；按勾选扩展名过滤（后缀不区分大小写）
   - 命中"排除目录"的整棵子树被跳过，并统计跳过的目录数
   - 结果按路径（小写）升序排列，保证日志顺序稳定
   - 扫描到 0 个文件 → 提示"没有找到可处理的文件"，中止
3. **确认**（仅实际模式，预览模式不弹、直接跑）
   - 弹确认框：标题 `确认风格化`，正文含文件数、目录、递归/备份选项，以及说明"只调整代码的缩进、空格与换行，不删除文件、不涉及硬盘格式化。是否继续？"
4. **逐文件处理**（后台 `threading.Thread`（daemon）+ `queue.Queue` 事件，串行；主线程 `after(60ms)` 轮询取事件刷新界面）
   - **预览模式**：把文件复制到 `%TEMP%\astyle_preview_xxx\`，对副本执行 astyle，比较复制前后副本内容 sha256 → 输出 `将会修改` / `无需修改`；每个副本处理完即删除，结束后删除临时目录。**原件字节零改动**。
   - **实际模式**：
     a. 若勾选备份 → 复制 `<file>` 为 `<file>.orig`（已存在则直接覆盖；备份失败该文件记 FAIL）
     b. 读入原文件字节 → `sha256`
     c. 调用 `astyle --options=<rc> --suffix=none <file>`（`shell=False`，单文件超时 60s）
     d. 再读字节 → `sha256`；两次不同 → `OK/已格式化`；相同 → `SKIP/无变化`
     e. 退出码非 0 → `FAIL`，附输出片段（若被 `--quiet` 抑制则记"退出码 N"）
   - 每处理完一个文件立刻发事件刷新一行日志与进度
   - 每个文件开始前检查一次停止标志
5. **汇总**：状态栏 + 日志末行 `完成：共 N，已格式化 A，无变化 B，失败 C，用时 T s`（预览模式为 `将会修改 A，无需修改 B，失败 C`）
   - 实际模式且 C>0 → 弹窗 `有 C 个文件处理失败，共处理 N 个文件。详见日志。`
   - 预览模式 → 弹窗 `A 个文件将会被修改，B 个无需修改。原文件未被改动。`
   - 中途停止 → 汇总行以"已停止"开头
6. **收尾**：恢复按钮可用状态；`self.worker = None`；日志文件句柄关闭。若用户在运行中请求了关窗，此时保存设置并退出。

### 4.4 备份语义

- 勾选"保留 .orig 备份"时，每个文件处理前都会生成 `.orig`（已有旧备份直接覆盖），`.orig` **恒等于"本次格式化前"的内容**。
- 文件实际被修改 → 保留 `.orig`；**无变化**（前后哈希相同）→ 把刚生成的备份删掉，避免目录里堆积与源文件完全相同的备份；删除失败仍按 `SKIP` 计数，日志记 `无变化（备份删除失败：原因）`。
- 未勾选备份 → 不生成任何 `.orig`。

### 4.5 日志规范

- 界面：`tk.Text`（只读、`wrap="none"`、`Consolas 10pt`、双向滚动条），插入后自动滚动到底，支持选中复制。
- 单行格式：`[HH:MM:SS] [STATUS] <相对路径>  <说明>  <耗时s>`
  - 路径显示**相对代码目录**的路径，避免超长。
  - STATUS 与配色：`OK` 绿、`SKIP` 灰、`FAIL` 红、`INFO` 默认色（`Text.tag_configure` 预定义标签逐行着色）。
- 日志文件：`<程序所在目录>\logs\astyle_YYYYMMDD_HHMMSS.log`，**UTF-8 带 BOM**（Windows 记事本友好），内容与界面一致（纯文本，无颜色），每行写入即 `flush`。目录不存在时自动创建。
- 失败行同时写 astyle 的 stderr/stdout 原文（单行化、截断至 300 字符；若为空则只写退出码）。

### 4.6 异常与边界处理

| 场景 | 处理 |
|---|---|
| astyle 路径不存在 / 不是 exe | 开始前弹窗拦截；"检测"按钮也提示 |
| rc 路径不存在 | 弹窗拦截（不提供"仅用默认风格继续"，避免和 Source Insight 效果不一致） |
| 目录无权限 / 文件被占用（返回非 0） | 记 FAIL 继续，不中断整批 |
| 文件是只读属性 | astyle 报错 → FAIL，其余文件继续 |
| 路径含中文/空格/`&` | 全程 `subprocess` 参数列表 + `pathlib`，禁用 shell 拼接 |
| astyle 卡死 | 单文件超时 60s（`subprocess.run(timeout=60)`），超时 → FAIL("执行超时") |
| 无法启动进程（OSError） | 记 FAIL（"无法启动 astyle：原因"），继续后续文件 |
| 用户在运行中关闭窗口 | 弹确认"文件正在处理中，确定中止并退出吗？" → 置中断标志，等当前文件结束（最多 `join` 3 秒）后再保存设置并退出 |
| 运行中重复点开始 | 开始/检测/清理备份按钮均已禁用，不会重入 |
| `.orig` 已存在 | 直接覆盖为本次格式化前的内容；若本次格式化无变化，则删除该 `.orig` |

---

## 5. 文件与模块划分

### 5.1 `ui_main.py` —— 只负责界面（不含任何 astyle / subprocess 逻辑）

```
DEFAULT_EXE / DEFAULT_RC          # 默认路径
LOG_DIR / SETTINGS_FILE           # 程序目录下的 logs\ 与 settings.ini

class Settings:                   # settings.ini 读写（configparser，[General] 段）
    get / get_path / get_bool / set / sync
def read_text_any(path) -> str    # utf-8-sig 优先，回退 gbk

class PlaceholderEntry(tk.Entry): # 带灰色占位提示的输入框
    get_text() / set_text()

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
- **不负责**：进程调用、文件扫描、哈希比较、日志落盘、按钮命令绑定——本文件不出现任何 `command=` / `protocol()` 绑定，全部由 `main.py` 的 `AppController._connect_signals()` 注册。
- 控件以 `self.btn_xxx` / `xxx_edit` / `xxx_var` 形式公开，业务层直接 `configure(command=...)`。

### 5.2 `main.py` —— 入口 + 全部逻辑

```
def now_ts() -> str
def decode_output(b) -> str            # utf-8 优先，失败回退 gbk，最后 latin-1
def sha256_file(p) -> str
def rel_path(path, root) -> str
def build_argv(exe, rc, target) -> list[str]
def run_astyle(exe, rc, target, timeout=60) -> tuple[int, str]
                                        # 退出码 <0 表示本程序层面失败（超时/无法启动）
def orig_path(p) -> Path               # <文件名>.orig 路径
def backup_file(p) -> tuple[str, str]  # (OK/FAIL, 说明)
def scan_files(root, extensions, recursive, excludes) -> tuple[list[Path], int]
                                        # (待处理文件, 被排除目录数)
def scan_orig_files(root, recursive) -> list[Path]
def validate_config(cfg) -> str | None # 返回错误文本，None 表示通过

class FormatWorker:                    # threading.Thread(daemon) 封装，串行处理
    def __init__(job: dict, events: queue.Queue)
    def start() / request_stop() / is_running() / join(timeout)
    def run()                          # 投递 ("log", 行, 级别)/("progress", done, total)/("done", stat)
    def _process_one(...)              # 实际格式化（含备份与哈希判定）
    def _preview_one(...)              # 预览：临时副本上真实格式化后比较

class LogFile:                         # 写 logs\astyle_YYYYMMDD_HHMMSS.log（UTF-8 BOM）
class AppController:                   # 业务控制器，_connect_signals() 是唯一的命令注册点
    def _pump()                        # after(60ms) 轮询 events 队列
    def on_pick_exe/on_pick_rc/on_view_rc/on_pick_code_dir/on_add_exclude
    def on_show_history/on_history_chosen/on_clear_history
    def on_check/on_start/on_stop/on_clean_orig/on_close_requested/on_done
    def _show_text_dialog(...)         # .astylerc 只读查看窗口（含"关闭"按钮）
def main()                             # MainWindow + load_settings + AppController + mainloop
```

- 负责：校验、扫描、备份、哈希判定、进程调用、超时、停止、历史目录（存 `settings.ini` 的 `history` 键，JSON 数组，最多 10 条）、日志落盘、汇总统计、弹窗触发（调用 UI 的 notify）。
- **线程纪律**：后台线程只往 `queue.Queue` 投事件，绝不碰控件（tk 只允许主线程更新界面）；主线程 `_pump()` 轮询消费。

### 5.3 目录结构

```
<程序目录>\
├── main.py            # 入口 + 全部业务逻辑（FormatWorker / AppController）
├── ui_main.py         # 界面层（tkinter：控件、界面原语、日志、弹窗、settings.ini）
├── settings.ini       # 界面配置（关闭窗口时写入，UTF-8 明文）
├── README.md
├── REQUIREMENTS.md    # 本文档
└── logs\              # 运行时自动生成
```

---

## 6. 技术方案要点

| 关注点 | 方案 |
|---|---|
| 进程调用 | `subprocess.run(argv_list, shell=False, capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW)` |
| 命令行构造 | `[exe, f"--options={rc}", "--suffix=none", str(file)]`；**不加**任何风格类参数，保证与 Source Insight 单文件效果逐字节一致 |
| 异步 | `threading.Thread`（daemon）跑 `FormatWorker`，只往 `queue.Queue` 投事件；主线程 `after(60ms)` 轮询刷新界面；停止用 `threading.Event` 协作式中止 |
| 编码 | 捕获 bytes → 先 `utf-8` 再 `gbk` 回退（中文 Windows 报错常为 GBK），最后 `latin-1` 兜底 |
| 结果判定 | 前后 `sha256` 对比（见 R1），失败看退出码 |
| 备份 | Python `shutil.copy2` 生成 `.orig`（见 R2） |
| 预览 | 复制到临时目录对副本真实格式化后比较（不用 `--dry-run`：`--quiet` 抑制输出且其退出码不可靠） |
| 设置持久化 | `configparser`（`interpolation=None`）读写 `settings.ini` 的 `[General]` 段，与 `main.py` 同目录，UTF-8 明文 |
| 单实例 | 不做，允许多开（风险低，自用） |
| 日志性能 | 每行 `Text.insert("end", line, tag)` + `see("end")` 一次，插入时临时 `state="normal"`、写完复位 `disabled`；文件句柄常开 `flush()` |

---

## 7. 明确不做（范围外）

- 不做风格规则编辑器（`.astylerc` 只读查看，编辑仍在外部）。
- 不做 Source Insight 集成/插件。
- 不做格式化前后 diff 预览。
- 不做多目录批量、不做多进程并发、不做按 mtime 过滤。
- 不做"一键还原 .orig"。
- 不打包 exe。
- 不做深色主题/皮肤、不做快捷键、不做拖放（tkinter 原生不支持控件级拖放）。

---

## 8. 验收标准

1. `python main.py` 能启动，窗口 3 秒内出现，无异常输出。
2. 首次启动三个路径框已填好 `D:\astyle\astyle.exe`、`D:\astyle\.astylerc`、空目录。
3. 选一个含 10 个以上 `.c/.h` 且有子目录的工程目录，点"开始"：
   - 每个文件日志一行，状态正确（有修改的显示 `OK`，无变化的显示 `SKIP`）
   - 勾选备份时只有被修改的文件生成 `xxx.c.orig`，且内容与格式化前一致
   - 处理后的文件用 git diff 检查，改动与 Source Insight 单文件执行结果**逐字节一致**
4. 勾选"预览模式"：所有文件 mtime 与内容零变化；日志给出"将会修改 / 无需修改"；结束后临时目录被清理。
5. 处理 500 个文件期间可拖动窗口、可点"停止"（2 秒内停下），界面不"未响应"。
6. 中文路径（如 `D:\工程\代码`）下正常处理，日志与窗口中文不乱码。
7. 关闭再打开，路径、勾选项、排除列表、窗口尺寸全部恢复。
8. `logs\` 下生成当次日志文件，用记事本打开中文正常。
9. 把 `.c` 文件设为只读后处理，该文件显示 `FAIL`、其余文件继续处理，结束后弹窗汇总失败数。
