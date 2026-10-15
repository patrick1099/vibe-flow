# 交接 · 2026-10-15

## 已谈定

- 2026-10-15 · 用户 · 应用界面效果图先行：原生 GUI 只靠文字需求让 AI 写，观感很差；新应用、新页面、布局大改先出 HTML 效果图，用户在浏览器里改到满意，再让 AI 照图实现。
- 2026-10-15 · 用户 · DESIGN.md 从 Web 分支上移，原生与 Web 共用，作为颜色、字体、间距的唯一来源；取消“单页不建”。
- 2026-10-15 · 用户 · 纯 Rust 原生 GUI 固定用 Slint；egui、iced 等其他 Rust UI 不再考虑。
- 2026-10-15 · 采纳 codex 建议 · designmd 0.4.0 导出不完整（css-vars 无字体；css-vars 与 dtcg 都不导 components；dtcg 丢无单位 lineHeight），不能当无损转换器，导不出的值不许静默丢；`omitted` 只表示设计有意不定义某节，不用来声明框架能力，能力清单写进语言参考；状态按实际功能选，用一个可切换状态的 HTML；Tk 字号 px 要写成负数；截图对照由 AI 先做、比观感不比像素、第一版布局出来就对照。
- 2026-10-15 · 用户（未反对 AI 提议）· 分两批：第一批只改 skill 文本；第二批写 DESIGN.md → ttk / Slint 主题生成器（生成器放插件、产物放项目、不支持的字段报错），等真实项目时再做。

## 待做：DESIGN.md → 原生主题生成器（效果图先行的第二批）

**状态**：第一批（0.22.0，skill 文本）已在分支 `feat/mockup-first-design-md` 完成，150 项回归通过。第二批没开工，**等用户下一个真实的 ttk 或 Slint 应用时再做**，不要凭空先写。

**现在怎么办**：原生主题由 AI 按项目根 `DESIGN.md` 手工搬进主题文件一处（ttk 的 `theme.py`、Slint 的 `ui/theme.slint`），规则在 `skills/vibe-apps/SKILL.md`「界面：效果图先行」与 `skills/vibe-apps-native/references/{python-ttk.md,rust.md}`「效果图与主题」。

**要做的**：
- 生成器放插件（建议 `skills/vibe-apps/scripts/`），生成结果放应用项目；应用运行、打包不依赖插件路径或 Node，只在改设计时跑。
- 流程：读 DESIGN.md 源数据先校验支持范围（v1 只认不透明 HEX 色、带单位的尺寸、字体族与支持的字重），不支持的字段**报错**，不静默丢——这一步必须看源数据，丢进导出后的 JSON 里已经发现不了。再用 `designmd export --format dtcg`（版本取 `skills/vibe-apps/vendor/design-md/cli-package.json`）拿 JSON，stdlib 读，不手写 YAML 解析器。
- 已知导出缺口（0.4.0，codex 实测）：css-vars 无字体；css-vars 与 dtcg 都不导 `components`；dtcg 丢无单位 `lineHeight`。
- 输出：效果图用的预览 CSS；ttk 项目主题（`ThemeDefinition` + `register_theme`，颜色槽位映射照 `python-ttk.md` 那张表，字号 px 写成负数）；Slint `export global Theme`（px 直接搬）。
- 验收：在真实 tk / Slint 窗口里实测字号单位和颜色映射，截图与效果图对照。主题生成后控件仍要自己消费这些值，hover / focus / disabled / selection 状态要单独核。

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
