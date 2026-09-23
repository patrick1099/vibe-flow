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
| 工具包 | >400 行，或第 3 个 Adapter 出现 | 机械拆为 `cli.py / core.py / ports.py / adapters/<轴>/<成员>.py`，依赖方向不变，见下「工具包级的变化轴」 |

拿不准时按标准级写。从标准级长成工具包是机械动作：五个区各自变成文件。

定级按代码本身，和 `vibe-flow` 的档位（流程厚度）无关：一个工具包级项目上的明确小改仍按省档流程走。**低耦合、文档、谁拍板的规矩以 `vibe-flow` §4–§6 为唯一权威出处**，本 skill 只给 Python 单文件 / 工具包的落法；两边说法不一致时以 `vibe-flow` 为准。微脚本也要逻辑和 IO 分开，做到「纯函数 ＋ `main()`」就够。

**文档（硬性，见 `living-blueprint`）**：微脚本用头部契约行代替；标准级和工具包级必须带 `BLUEPRINT.md` ＋ `CHANGELOG.md`；有没做完的活时再加 `HANDOFF.md`，做完删掉。独立目录的放 `docs/`，和别的脚本共处一个目录的放同名旁挂文件 `<脚本名>.BLUEPRINT.md` / `.CHANGELOG.md` / `.HANDOFF.md`。**工具包级另带项目根 `AGENTS.md`**，下面的「改动菜单」照项目实际填进它的代码地图；单文件脚本由头部 `结构:` 行代替 AGENTS.md。

## 四层五区模板（标准级）

依赖方向固定：**App → Core → Port ← Adapter**。Core 永不知道 Adapter 的存在。

```python
# 结构: vibe-scripts/standard
# 用途: <一句话>
# 用法: py -3 xxx.py parse log.txt
# 原始需求: <生成本脚本时的需求描述原文，供未来重生成/大改时使用>

# ===== 1 配置/常量 =====
DEFAULT_BAUD = 9600

# ===== 2 Port：接口定义（只有一种 IO 实现时省掉本区，Core 直接收数据）=====
class Transport:                      # 或 typing.Protocol
    def transact(self, frame: bytes) -> bytes: raise NotImplementedError

# ===== 3 Core：纯逻辑（只调 Port；禁止 open/serial/socket/print）=====
def decode_frame(frame: bytes) -> dict: ...

# ===== 4 Adapter：实现 + 注册（示例是“真实串口 / 仿真”两种正式运行方式）=====
class SerialTransport(Transport): ...
class SimTransport(Transport):        # 仿真是正式运行方式，走注册表，不是 if 分支
    def __init__(self, replyfile): ...
TRANSPORTS = {"serial": SerialTransport, "sim": SimTransport}

# ===== 5 App：命令表 + CLI 入口（调度组合、负责打印）=====
def cmd_send(args):
    tp = TRANSPORTS[args.transport](...)   # 传输选择只发生在这一行
    ...
COMMANDS = {"parse": cmd_parse, "send": cmd_send}
```

## 硬规则

1. **外部 IO 不进 Core**：串口 / 网络 / 子进程 / 真实设备的读写放 Adapter 区，Core 只收数据、只返回数据。只有一种 IO 实现时，Adapter 区写普通函数就行，不必定义 Port 类。工具正式提供第二种运行方式（最常见是“真实设备 / 仿真”）时，才定义 Port、把两种实现注册进 `TRANSPORTS` 表——**禁止在命令函数里写 `if args.sim:` 这类传输分支**（最常见走样：传输选择散落进每个命令，加传输方式或加收发类子命令时改动发散）。只在测试里用的假对象是测试替身，直接在测试里构造，不进注册表。
2. **扩展点从第二个成员起是表**：子命令、厂商、格式、传输出现第二个成员时，收成 dict/list 注册，加能力 = +1 表项 +1 函数。禁止 if-elif 链扩展。子命令表是例外——有子命令就直接用 `COMMANDS` 表，成本几乎为零。
3. **Core 区纯函数**：不 open、不 import serial、不 print。算出数据返回，打印归 App 层。纯函数可直接被 `--self-test` 和未来 AI 单独验证。
4. **头部四行契约**（结构/用途/用法/原始需求）必写：`结构:` 行让未来 AI 会话免通读直达分区；`原始需求:` 行是重生成锚点。

## 工具包级的变化轴（多文件时可插拔怎么落）

单文件时「一切扩展点都是表」一张 dict 就够；拆成多文件后，同一类成员（平台、厂商、格式、后端）最容易散：名单在 A 文件写一遍、B 文件 `if x in (...)` 再判一遍，拔一个成员就要全仓扫。落法：

```python
# adapters/platforms/__init__.py —— 这条轴唯一的名单；只登记名字，不在这里导入成员
import importlib
PLATFORMS = ("alpha", "beta")

def load(name):
    return importlib.import_module(f"{__name__}.{name}")

def load_all():
    ok, bad = {}, {}
    for name in PLATFORMS:
        try:
            ok[name] = load(name)
        except Exception as e:          # 一个成员导入失败只标它自己
            bad[name] = repr(e)
    return ok, bad

# adapters/platforms/alpha.py —— 成员的一切都在这一个文件里
CAPS = {"views", "links"}          # 能力由成员自己声明
def check(ctx) -> list[str]: ...  # 返回问题列表，不抛到上层
```

- **名单只有一份**：别处需要成员列表（CLI 的 `choices`、循环、校验），一律从注册表取，不许再手写一遍。
- **按能力分支问成员**：`if "links" in p.CAPS`，禁止 `if name in ("alpha", "beta")`。
- **故障隔离**（成员各自依赖第三方库、设备、网络时才需要，上面的惰性加载写法就是为这个）：一个成员导入失败不影响注册表本身。聚合类命令用 `load_all()`，把 `bad` 里的成员报成“不可用 ＋ 原因”，其余照常跑，退出码按汇总结果定；用户点名要的成员加载失败，就明确报错、非零退出。成员只是几个纯函数时，`PLATFORMS = {"alpha": alpha_fn, ...}` 一张 dict 就够。
- **结构测试**（好档、本次新建或收口了轴时）：① 往注册表塞一个假成员，CLI 选项和聚合命令都能看到它；② 做了故障隔离的，让一个成员导入时抛错，其余成员和聚合命令照常工作。

## 六模式速查

| 需求特征 | 模式 | 形态 | 适用度 |
|---|---|---|---|
| 多个子命令 | Command | `COMMANDS` dict | 标准级必用 |
| 功能模块可插拔 | Plugin/Registry | `register(name, handler)` 统一注册 | 第 2 个成员出现时引入 |
| IO 可换（串口/文件/仿真）| Ports & Adapters | Port 类 + `TRANSPORTS` 表 | 有第二种正式运行方式时引入；只有一种 IO 时 Adapter 区写函数即可 |
| 区/模块边界 | Facade | 每区只暴露 1~3 个函数给上层 | 标准级建议 |
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
- 微脚本套四层五区全套
- 头部没有 `结构:` 契约行
- 工具包里同一类成员的名单手写在多处，或按名单 `if name in (...)` 分支
- 一个成员（适配器）出错让整条命令崩掉；注册表顶层一次性导入全部成员
- 标准级以上交付时没有 `BLUEPRINT.md` / `CHANGELOG.md`
- 只有一种 IO 实现却预建 Port 类和注册表；或把测试替身注册进运行时 `TRANSPORTS`

## 环境约定

`py -3`；stdlib 优先，不建 venv；源文件 UTF-8；路径处理兼容 Windows。
