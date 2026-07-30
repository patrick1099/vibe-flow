---
name: vibe-scripts
description: Use when writing or modifying any standalone Python script or small tool (写脚本、小工具、自动化、数据处理、抓包分析、批量转换、串口调试工具) that is NOT part of a product/firmware/build codebase — load BEFORE generating the script, and when adding subcommands, vendor/format variants, or new IO sources to an existing script.
---

# vibe-scripts：Python 小脚本架构模板

## 总纲

> 核心稳定，边缘可换；接口显式，注册集中；功能纵切，增量可测。

省 token 原理：AI 改代码的成本 ∝ 它必须读的代码量。本模板让任何一类改动只需读/改一个固定小区域。

**适用判定**：这段代码坏了产品会坏吗？会 → 不适用（走项目编码规范 + 人审）；不会（独立脚本/工具）→ 适用。有界面 / 要发给别人(exe) / 可能变网站 → 改用 **vibe-apps**（本 skill 只管命令行单文件脚本）。

## 第一步：定级（先定级，再写代码）

| 级别 | 判定 | 架构要求 |
|---|---|---|
| 微脚本 | <100 行、单一功能、IO 形式单一 | 纯函数 + `main()` 两段即可，**禁止**套四层五区（过度工程同样浪费 token）|
| 标准（默认）| 有子命令，或有变体（厂商/格式/版本），或有可替换 IO | 单文件四层五区，见下 |
| 工具包 | >400 行，或第 3 个 Adapter 出现 | 机械拆为 `cli.py / core.py / ports.py / adapters/`，依赖方向不变 |

拿不准时按标准级写。从标准级长成工具包是机械动作：五个区各自变成文件。

与 `vibe-flow` 档位的对应：**省档**落微 / 标准级，**好档**才考虑工具包级（判档在 `vibe-flow` §2，本 skill 不重判）。

**工具包级 / 会长期迭代的脚本**：建议配合 **`living-blueprint`** 维护 `docs/BLUEPRINT.md`（工具活蓝图，只讲功能不讲实现，纯手动触发）（微/标准级跑完即弃的通常不必）。

## 四层五区模板（标准级）

依赖方向固定：**App → Core → Port ← Adapter**。Core 永不知道 Adapter 的存在。

```python
# 结构: vibe-scripts/standard
# 用途: <一句话>
# 用法: py -3 xxx.py parse log.txt
# 原始需求: <生成本脚本时的需求描述原文，供未来重生成/大改时使用>

# ===== 1 配置/常量 =====
DEFAULT_BAUD = 9600

# ===== 2 Port：接口定义（脚本需要哪些外部能力）=====
class Transport:                      # 或 typing.Protocol
    def transact(self, frame: bytes) -> bytes: raise NotImplementedError

# ===== 3 Core：纯逻辑（只调 Port；禁止 open/serial/socket/print）=====
def decode_frame(frame: bytes) -> dict: ...

# ===== 4 Adapter：实现 + 注册（真实现与 mock 必须成对出现）=====
class SerialTransport(Transport): ...
class SimTransport(Transport):        # mock 是一等公民，不是 if 分支
    def __init__(self, replyfile): ...
TRANSPORTS = {"serial": SerialTransport, "sim": SimTransport}

# ===== 5 App：命令表 + CLI 入口（调度组合、负责打印）=====
def cmd_send(args):
    tp = TRANSPORTS[args.transport](...)   # 传输选择只发生在这一行
    ...
COMMANDS = {"parse": cmd_parse, "send": cmd_send}
```

## 硬规则

1. **外部 IO 必须过 Port**：串口/网络/子进程/真实设备一律定义 Port 接口。仿真/mock 是注册进表的一个 Adapter——**禁止在命令函数里写 `if args.sim:` 这类传输分支**（这是最常见走样：传输选择散落进每个命令，加传输方式或加收发类子命令时改动发散）。
2. **一切扩展点都是表**：子命令、厂商、格式、传输 = dict/list 注册，加能力 = +1 表项 +1 函数。禁止 if-elif 链扩展。
3. **Core 区纯函数**：不 open、不 import serial、不 print。算出数据返回，打印归 App 层。纯函数可直接被 `--self-test` 和未来 AI 单独验证。
4. **头部四行契约**（结构/用途/用法/原始需求）必写：`结构:` 行让未来 AI 会话免通读直达分区；`原始需求:` 行是重生成锚点。

## 六模式速查

| 需求特征 | 模式 | 形态 | 适用度 |
|---|---|---|---|
| 多个子命令 | Command | `COMMANDS` dict | 标准级必用 |
| 功能模块可插拔 | Plugin/Registry | `register(name, handler)` 统一注册 | 标准级必用 |
| IO 可换（串口/文件/模拟）| Ports & Adapters | Port 类 + `TRANSPORTS` 表 | 有外部 IO 即必用 |
| 区/模块边界 | Facade | 每区只暴露 1~3 个函数给上层 | 标准级必用 |
| 多厂商/版本/格式 | Strategy | `VENDORS`/`STRATEGIES` 表 | 第 2 个变体出现时引入 |
| 进度/事件通知 | Event/Observer | `on_progress`/`on_frame` 回调参数 | 仅长时运行类（采样、监控）|

## 改动菜单（未来会话照此导航，勿通读全文）

| 改动类型 | 只需读 | 只需改 |
|---|---|---|
| 加子命令 | 5 区命令表 + 一个同类命令 | +1 表项 +1 函数（+argparse 参数注册几行）|
| 换/加数据来源 | 2 区 Port 定义 | 4 区 +1 Adapter +1 表项 |
| 加厂商/格式变体 | 对应 Strategy 表 | +1 表项 +1 函数 |
| 改算法/解析逻辑 | 3 区目标函数 | 该函数本身 |

## 反模式（出现即返工）

- 命令函数里 `if sim: ... else: serial...`（传输分支散落）
- 用 if-elif 识别厂商/格式而不是注册表
- Core 里直接 IO 或 print
- 真 Adapter 没有配对的 mock Adapter
- 微脚本套四层五区全套
- 头部没有 `结构:` 契约行

## 环境约定

`py -3`；stdlib 优先，不建 venv；源文件 UTF-8；路径处理兼容 Windows。
