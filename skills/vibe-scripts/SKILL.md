---
name: vibe-scripts
description: Use when writing or modifying any standalone Python script or small tool (写脚本、小工具、自动化、数据处理、抓包分析、批量转换、串口调试工具) that is NOT part of a product/firmware/build codebase — load BEFORE generating the script, and when adding subcommands, vendor/format variants, or new IO sources to an existing script.
---

# vibe-scripts：Python 小脚本架构模板

## 总纲

> 核心稳定，边缘可换；接口显式，注册集中；功能纵切，增量可测。

省 token 原理：AI 改代码的成本 ∝ 它必须读的代码量。本模板让任何一类改动只需读/改一个固定小区域。

**适用判定**：这段代码坏了产品会坏吗？会 → 不适用（走项目编码规范 + 人审）；不会（独立脚本/工具）→ 适用。有界面 / 要发给别人(exe) / 可能变网站 → 改用 **vibe-apps**。

**分工**：判档、低耦合规矩、文档要求、谁拍板，都以 `vibe-flow` 为准（§2、§4–§6），本 skill 只给 Python 脚本的落法。**新写脚本或调整结构时，读 `references/templates.md` 拿模板代码。**

## 第一步：定级（先定级，再写代码）

| 级别 | 判定 | 架构要求 |
|---|---|---|
| 微脚本 | <100 行、单一功能、IO 形式单一 | 纯函数 + `main()` 两段即可，**禁止**套四层五区（过度工程同样浪费 token）|
| 标准（默认）| 有子命令，或有变体（厂商/格式/版本），或有可替换 IO | 单文件四层五区：1 配置 / 2 Port / 3 Core / 4 Adapter / 5 App，依赖方向 **App → Core → Port ← Adapter** |
| 工具包 | >400 行，或第 3 个 Adapter 出现 | 机械拆为 `cli.py / core.py / ports.py / adapters/<轴>/<成员>.py`，依赖方向不变 |

拿不准时按标准级写。从标准级长成工具包是机械动作：五个区各自变成文件。定级按代码本身，和 `vibe-flow` 的档位无关：工具包级项目上的明确小改仍按省档流程走。

## 硬规则

1. **外部 IO 不进 Core**：串口 / 网络 / 子进程 / 真实设备的读写放 Adapter 区，Core 只收数据、只返回数据。只有一种 IO 实现时，Adapter 区写普通函数就行，不必定义 Port 类。工具正式提供第二种运行方式（最常见是“真实设备 / 仿真”）时，才定义 Port、把两种实现注册进 `TRANSPORTS` 表——**禁止在命令函数里写 `if args.sim:` 这类传输分支**（最常见走样：传输选择散落进每个命令，加传输方式时改动发散）。只在测试里用的假对象是测试替身，直接在测试里构造，不进注册表。
2. **扩展点从第二个成员起是表**：厂商、格式、传输出现第二个成员时，收成 dict/list 注册，加能力 = +1 表项 +1 函数。禁止 if-elif 链扩展。子命令例外——有子命令就直接用 `COMMANDS` 表，成本几乎为零。
3. **Core 区纯函数**：不 open、不 import serial、不 print。算出数据返回，打印归 App 层。纯函数可直接被 `--self-test` 和未来 AI 单独验证。
4. **头部四行契约**（结构 / 用途 / 用法 / 原始需求）必写：`结构:` 行让未来 AI 会话免通读直达分区，也是文档闸认出 vibe 脚本的标记；`原始需求:` 行是重生成锚点。

## 工具包级的变化轴

拆成多文件后，同一类成员（平台、厂商、格式、后端）最容易散：名单在 A 文件写一遍、B 文件 `if x in (...)` 再判一遍，拔一个成员就要全仓扫。

- **名单只有一份**：`adapters/<轴>/__init__.py` 放注册表，每个成员一个文件。别处要成员列表（CLI 的 `choices`、循环、校验）一律从注册表取。
- **按能力分支问成员**：`if "links" in p.CAPS`，禁止 `if name in ("alpha", "beta")`。
- **故障隔离只在成员各有外部依赖时做**：注册表只登记名字、惰性加载；聚合类命令把加载失败的成员报成“不可用 ＋ 原因”，其余照常跑，退出码按汇总结果定；用户点名要的成员加载失败，明确报错、非零退出。成员只是几个纯函数时一张 dict 就够。
- **结构测试**（好档、本次新建或收口了轴时）：① 往注册表塞一个假成员，CLI 选项和聚合命令都能看到它；② 做了故障隔离的，让一个成员导入时抛错，其余照常工作。

## 六模式速查

| 需求特征 | 模式 | 形态 | 适用度 |
|---|---|---|---|
| 多个子命令 | Command | `COMMANDS` dict | 标准级必用 |
| 功能模块可插拔 | Plugin/Registry | `register(name, handler)` 统一注册 | 第 2 个成员出现时引入 |
| IO 可换（串口/文件/仿真）| Ports & Adapters | Port 类 + `TRANSPORTS` 表 | 有第二种正式运行方式时引入 |
| 区/模块边界 | Facade | 每区只暴露 1~3 个函数给上层 | 标准级建议 |
| 多厂商/版本/格式 | Strategy | `VENDORS`/`STRATEGIES` 表 | 第 2 个变体出现时引入 |
| 进度/事件通知 | Event/Observer | `on_progress`/`on_frame` 回调参数 | 仅长时运行类（采样、监控）|

## 改动菜单（未来会话照此导航，勿通读全文）

| 改动类型 | 只需读 | 只需改 |
|---|---|---|
| 加子命令 | 5 区命令表 + 一个同类命令 | +1 表项 +1 函数（+argparse 参数注册几行）|
| 换/加数据来源 | 2 区 Port 定义（没有就先按硬规则 1 建） | 4 区 +1 Adapter +1 表项 |
| 加厂商/格式变体 | 对应 Strategy 表 | +1 表项 +1 函数 |
| 改算法/解析逻辑 | 3 区目标函数 | 该函数本身 |

独占目录的工具包，把这张表按项目实际填进 `AGENTS.md` 的代码地图。

## 环境约定

`py -3`；stdlib 优先，不建 venv；源文件 UTF-8；路径处理兼容 Windows。
