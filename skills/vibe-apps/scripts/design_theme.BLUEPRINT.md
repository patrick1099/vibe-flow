# design_theme 蓝图
> 活蓝图：正文永远是当前真相，改了就覆盖。只讲功能不讲实现。
> 重构照本文行为契约重写即可；未列为硬约束的一切都是实现细节，可自由更改。

## 1. 一句话
给 AI 在改原生应用设计时调用：读项目根 `DESIGN.md`，校验后生成 ttk 或 Slint 的主题文件，并把同一批值写进效果图 HTML，让效果图、主题、代码出自一处。

## 2. 功能与行为 + I/O 契约
- 生成：给 `<ttk|slint> --design <DESIGN.md>` → 写主题文件，刷新效果图里的 token 块，stdout 一行成功信封，`data.files[]` 列出每份的 `kind`（theme / mockup）、`path`、`status`（created / updated / unchanged / skipped）。内容没变的文件不重写。
- 校验：DESIGN.md 有子集外写法或超出 v1 范围的值 → 一份都不写，stderr 失败信封 `E_VALIDATION`，`details.problems[]` 一次列出全部问题（`line`、`where` 如 `colors.selection`、`message` 含改法），按行号排序。
- `--check`：不写文件；任何产物缺失或与 DESIGN.md 不一致 → `E_VERIFICATION_FAILED`、退出 1，`details.files` 说明哪份过期；效果图不存在不算过期。
- `--dry-run`：不写文件，信封照常报告各份会怎样变化，`data.dry_run: true`。
- 效果图：默认 `<DESIGN.md 目录>/docs/mockup/index.html`；不存在 → `status: skipped` 并给出原因；存在但没有、或有多个 `<style id="design-tokens">` 块 → `E_VALIDATION`，文件不动。
- `--ai-help`：在解析参数之前输出 Markdown 使用说明（带 `name / description / ai_help_version` front matter），退出 0；`--` 之后的 `--ai-help` 不算。`--json` / `--format json` 接受但无作用，输出始终是 JSON。

**I/O / 数据契约（换语言必须逐字保留）**：
- 输入：DESIGN.md 的 front matter（首行 `---` 到下一个 `---`）。只认块状写法：两层映射，typography 三层；标量为引号字符串、整数、小数、普通字符串；缩进只用空格。锚点、`{}` / `[]` 行内写法、`|` / `>` 多行块、tab、重复键、带引号的键名、未加引号的 `#色值`、`yes`/`null` 这类歧义值一律报错；`version` `name` `description` `omitted` 整段不参与生成，里面写什么都不管。
- v1 支持范围：颜色 `#RGB` / `#RRGGBB`（slint 另收 `#RGBA` / `#RRGGBBAA`，统一输出小写全长 hex）；spacing、rounded、fontSize 只认 `px`；typography 认 `fontFamily`（单个字体族，不许逗号列表）、`fontSize`（必填）、`fontWeight`（100–900 整百，缺省 400）。报错：rgb()/颜色名、em/rem、无单位数、`lineHeight`、`letterSpacing`、`fontFeature`、`fontVariation`、未知属性、`components` 段、未知顶层字段。
- ttk 额外：16 个颜色槽位要的 token 缺一个就报错（primary secondary success info warning error base-100 base-content base-200 neutral selection selection-content border input input-content active，映射照 `vibe-apps-native/references/python-ttk.md` 的表）；不收透明色；字重只 400 / 700；字号、间距、圆角要整数像素。
- slint 额外：生成后的属性名要是合法 Slint 标识符（字母或 `_` 开头），且 `_` 与 `-` 视为相同时不得重名。
- 输出 ttk：默认 `<DESIGN.md 目录>/design_tokens.py`，纯数据，不 import 任何库：`TTK_COLORS`（ttkbootstrap 16 槽位名 → 色值）、`COLORS`（全部 token 名 → 色值）、`FONTS`（名 → `(族, -像素, "normal"|"bold")`）、`SPACING`、`ROUNDED`（名 → 整数像素）。
- 输出 slint：默认 `<DESIGN.md 目录>/ui/theme.slint`，`export global Theme`：颜色 `out property <color> <token>`；`spacing-<名>`、`rounded-<名>` 为 `<length>`；每个字体 `<名>-family`（string）、`<名>-size`（length）、`<名>-weight`（int）。
- 效果图 token 块：`:root` 上的 `--color-<名>`、`--spacing-<名>`、`--rounded-<名>`、`--font-<名>-family|size|weight`；块外内容一字不动，换行风格跟随原文件。
- 每份产物首行注明“由 design_theme.py 从 DESIGN.md 生成，勿手改”和 `source-sha256`（front matter 换行归一后的前 12 位；改正文不算设计变了）。产物不含时间戳，同一输入重跑逐字相同。
- 退出码：0 成功（含 dry-run）；1 运行失败（`E_VALIDATION` 内容不合要求、`E_NOT_FOUND` 找不到 DESIGN.md、`E_VERIFICATION_FAILED`、`E_IO` / `E_PERMISSION`、`E_INTERNAL`）；2 参数错误（`E_VALIDATION`）。失败信封走 stderr，stdout 为空。

## 3. 边界 / 明确不做
- 只出颜色、字体、间距、圆角；不生成控件样式、不处理 `components`。
- 只出一套颜色，不做深浅色切换；要切换的项目（如 serial-split 的 `dark: bool`）照旧手写 Theme。
- Web 路线不用它，仍用 `designmd export`。
- 不调 node、不联网、不调外部程序；不代替 `designmd lint` 做规范检查（流程里先 lint 再跑它）。

## 4. 硬约束 + 重构自由声明
- 只用 Python 标准库，`py -3` 直接跑；不建 venv。
- 校验必须看 DESIGN.md 源数据，不以任何导出结果为输入；超出范围一律报错，不静默丢、不悄悄换算。
- 不支持的写法全部列出后才失败；失败时一份产物都不写。
- 写文件先写同目录临时文件再替换；临时文件保留目标扩展名（本机 Esafenet 拒绝把别的扩展名改名成受加密的 `.py` / `.css`，报 WinError 17）。
- 效果图的 token 写进 HTML，不另建 `.css`（本机 Esafenet 加密 python 写出的 `.css`，浏览器读到密文）。
- 变化轴：加或去掉一个输出目标，只动它自己的适配器和这张表（`TARGETS`）。CLI 的目标选项从这张表派生。
- **以上未列出的一切均为实现细节，重构可随意更改。**

## 5. 功能痛点 / 易错点
- YAML 里 `primary: #2563eb` 的值是注释、等于没写，必须提示加引号，不能当空映射放过。
- 原生框架的字号单位：Tk 正数是点、负数是像素，必须输出负数；Slint 的 `px` 是逻辑像素，和 CSS 一一对应。
- `lineHeight` 看似能搬：DESIGN.md 的倍数乘字号，Slint 的 `line-height-factor` 乘字体自然行高，含义不同，所以 v1 拒绝。
- 主题只管颜色和字体；控件尺寸（如 ttkbootstrap 按钮内边距）、Slint 的粗体字体文件注册、截图时的缩放固定，都在应用里处理，截图对照时核。
