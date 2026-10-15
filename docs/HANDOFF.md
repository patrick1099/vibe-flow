# 交接 · 2026-10-15

## 已谈定

- 2026-10-15 · 用户 · 应用界面效果图先行：原生 GUI 只靠文字需求让 AI 写，观感很差；新应用、新页面、布局大改先出 HTML 效果图，用户在浏览器里改到满意，再让 AI 照图实现。
- 2026-10-15 · 用户 · DESIGN.md 从 Web 分支上移，原生与 Web 共用，作为颜色、字体、间距的唯一来源；取消“单页不建”。
- 2026-10-15 · 用户 · 纯 Rust 原生 GUI 固定用 Slint；egui、iced 等其他 Rust UI 不再考虑。
- 2026-10-15 · 采纳 codex 建议 · designmd 0.4.0 导出不完整（css-vars 无字体；css-vars 与 dtcg 都不导 components；dtcg 丢无单位 lineHeight），不能当无损转换器，导不出的值不许静默丢；`omitted` 只表示设计有意不定义某节，不用来声明框架能力，能力清单写进语言参考；状态按实际功能选，用一个可切换状态的 HTML；Tk 字号 px 要写成负数；截图对照由 AI 先做、比观感不比像素、第一版布局出来就对照。
- 2026-10-15 · 用户（未反对 AI 提议）· 分两批：第一批只改 skill 文本；第二批写 DESIGN.md → ttk / Slint 主题生成器（生成器放插件、产物放项目、不支持的字段报错）。
- 2026-10-15 · 用户 · 第二批现在就开始做，不再等真实项目（推翻上一条里的“等真实项目时再做”）。
- 2026-10-15 · 用户 · serial-split 保持现状：运行中参数照旧置灰，不加 HEX 行的 ASCII 列。

## 在做：DESIGN.md → 原生主题生成器（效果图先行的第二批）

**状态**：第一批（0.22.0 skill 文本，0.22.1 按 `my-repos/serial-split` 修正 Slint 参考，0.22.2 截图对照改查“像不像”）已合进 main 并发布。第二批**用户已叫开工**（2026-10-15），目前只做了事实摸底，**还没出方案、没写代码**。判档：好档·轻（新工具、三种输出）——方案要先过 codex 一次再动手。

**下一步（按顺序）**：
1. 验证 Slint 的 `slint!` 宏能不能 `import` 外部 `.slint` 文件。这决定 Slint 输出是“生成一个 `theme.slint` 文件”还是“生成一段要贴进宏里的文本”。用一个最小测试 crate 试，工具链照 `my-repos/serial-split` 的 README（`stable-x86_64-pc-windows-gnullvm` + llvm-mingw 的 `bin` 放 PATH 最前，`-j 2`），Slint 版本对齐 serial-split 的 1.18.1。
2. 写三点短设计 + 变化轴（输出目标 css / ttk / slint 已是 3 个实际成员 → 一份注册表 + 每目标一个适配器，按 `vibe-flow` 的 `references/low-coupling.md`），连同下面“待定”交 codex 审（`ai-room ask --to codex`，cwd 用本插件仓）。
3. 实现前加载 `vibe-scripts` 和 `xu-skills:cli-ai-spec`（脚本给 AI 调：一行 JSON 信封、退出码 0/1/2，参照同目录 `sync_upstream.py` 的写法）；在 worktree 里写、写测试。
4. 真窗口验收：ttk 窗口（ttkbootstrap 2.2.3 + Pillow 12.3）与 Slint 测试窗口，按 `skills/vibe-apps/SKILL.md` 第 5 步截图对照。
5. 收工：派 fork 更新 README 沿革 / 本文件，bump 0.23.0，合并、推子仓、`hub sync --refresh`（调法见共享记忆 `reference_hub_cli_invocation`）。注意：本次 HANDOFF 更新只提交在本地 main，没 bump、没推；在 bump 之前跑 `hub refresh` 会被 `PluginBumpNeeded` 拦，属正常，随 0.23.0 一起推。

**已摸清的事实（2026-10-15 用 designmd 0.4.0 实测，样例 DESIGN.md 含 rgba 色、无单位 spacing、无单位 lineHeight、components）**：
- CLI 只有 `lint | diff | export | spec`；export 格式：`css-tailwind`、`json-tailwind`（= `tailwind`）、`dtcg`、`css-vars`。
- `lint --format json` 只给 findings（警告 / 错误 / 计数），**不给解析后的 token**；有警告时退出码仍是 0。把颜色定义了却没被 component 引用会报 `orphaned-tokens` 警告——原生项目 DESIGN.md 多半不写 components，这类警告要容忍。
- **无单位的 spacing（`md: 8`）被静默丢弃**：lint 的计数和所有导出都没有它，可规范写的是 `Dimension | number`。这正是“只看导出发现不了”的例子。
- `rgba(...)` 色被接受，导出成 8 位 hex（`#2563eb4d`）；dtcg 的 `components` 数组丢了 alpha，只有 `hex` 字段带着。
- dtcg：颜色 / spacing / rounded / typography（fontFamily、fontSize、fontWeight）都有，丢无单位 lineHeight，无 components。json-tailwind：颜色、fontFamily、fontSize（带 fontWeight）、borderRadius、spacing，无 lineHeight。css-vars：只有颜色、spacing、rounded。

**待定（交 codex 审时一起问）**：
- 校验要看源数据，但 stdlib 解析不了 YAML。三条路：① 只认一个窄子集（两层映射 + 标量）的手写 front matter 读取器，子集外一律报错；② PyYAML 放 venv；③ 写个 node 小脚本直接用 `@google/design.md` 包里的解析器。之前写的“不手写 YAML 解析器”是在不知道导出会静默丢字段时定的，要重新权衡。
- ttk 输出的形式：生成一个 `design_tokens.py`（常量 + 颜色槽位字典，项目的 `theme.py` 导入后 `register_theme`），还是 JSON（运行时读、打包要带上）。倾向前者（PyInstaller 不用额外收文件）。
- 深色主题：DESIGN.md 规范只有一套颜色；serial-split 用 Theme 里的 `dark: bool` 切换。v1 是否只做单套。
- 8 位 hex（带透明度）在 ttk 里不支持，按“不支持就报错”处理。

**现在怎么办**：原生主题由 AI 按项目根 `DESIGN.md` 手工搬进主题一处（ttk 的 `theme.py`；Slint 是 `global Theme`，写在 `slint!` 宏里或 `ui/*.slint` 里都行，serial-split 是前者），规则在 `skills/vibe-apps/SKILL.md`「界面：效果图先行」与 `skills/vibe-apps-native/references/{python-ttk.md,rust.md}`「效果图与主题」。

**要做的**：
- 生成器放插件（建议 `skills/vibe-apps/scripts/`），生成结果放应用项目；应用运行、打包不依赖插件路径或 Node，只在改设计时跑。
- 流程：读 DESIGN.md 源数据先校验支持范围（v1 只认不透明 HEX 色、带单位的尺寸、字体族与支持的字重），不支持的字段**报错**，不静默丢——这一步必须看源数据，丢进导出后的 JSON 里已经发现不了。再用 `designmd export --format dtcg`（版本取 `skills/vibe-apps/vendor/design-md/cli-package.json`）拿 JSON，stdlib 读，不手写 YAML 解析器。
- 已知导出缺口（0.4.0，codex 实测）：css-vars 无字体；css-vars 与 dtcg 都不导 `components`；dtcg 丢无单位 `lineHeight`。
- 输出：效果图用的预览 CSS；ttk 项目主题（`ThemeDefinition` + `register_theme`，颜色槽位映射照 `python-ttk.md` 那张表，字号 px 写成负数）；Slint `export global Theme`（px 直接搬）。
- 验收：在真实 tk / Slint 窗口里实测字号单位和颜色映射，按 `skills/vibe-apps/SKILL.md` 第 5 步做截图对照（同尺寸、同状态、同数据，差异清单覆盖布局、控件状态、显示内容；Slint 截图写法参考 serial-split 的 `examples/ui_smoke.rs`）。主题生成后控件仍要自己消费这些值，hover / focus / disabled / selection 状态要单独核。

## 仍在试行的架构沟通

宏观复查的五条整改已全部完成（0.18.0–0.20.1，见 README「沿革」），相关约定已迁进 README 正文和沿革；下面只剩一件进行中的试行。

**在做**：试行"架构层只看"。用户懂架构概念（模块、数据流、流程图），不懂具体语言和代码。0.13.2 起「我打算怎么搭」图在好档、本次动到多个模块时默认画，架构词首次带解释即可用；0.13.3 按 codex 补审收紧（一条明显路也画、图上内部疑点不问用户、clarify-needs 的旧口径收窄）。规则在 `skills/vibe-flow/SKILL.md` §4 和 `clarify-needs/references/run-model.md`。

**试行的规矩**：架构层照旧由 AI（加 codex）定，但画给用户看、附一两句理由，不等回复就开工。用户开口时：明确要改的照改，提问的先解释，给建议的先判断采不采纳。代码层（语言、库、HTML 怎么写）照旧不问用户。

**试行记录**（每做完一个画了「我打算怎么搭」图的大活，补一行：日期 · 任务 · 用户看图后的主要反馈）：
- （暂无）

**回头看的节点**：记满两三行之后，拿这几个实际例子问用户一次：**继续先看后反馈，还是有哪些架构取舍想提前自己选？** 不要只凭插话多少自己下结论——插话多可能只是在纠正需求或问理由。
- 用户想提前自己选 → 把他点名的那类架构取舍写进 §4 决策边界（给两三条路、翻译成后果、由他拍板）；
- 用户觉得现在这样就行 → 保持"只看"，删掉 README「沿革」里"这是试行"那句和本文件。

**别碰**："方案定稿后不等回复就开工"不变。
