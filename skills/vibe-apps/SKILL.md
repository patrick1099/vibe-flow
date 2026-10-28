---
name: vibe-apps
description: Route personal GUI apps to native desktop or Web UI before scaffolding, discuss a project-appropriate architecture (Clean layering when warranted; presentation state follows the framework's own bindings), and apply the mockup-first UI flow (DESIGN.md + HTML mockup + screenshot comparison) and delivery checks. GUI、上位机、桌面工具、Web 界面、打包应用、界面效果图、DESIGN.md、照图实现；支持用户明确选择 Python 或纯 Rust（Slint）。Load after vibe-flow; standalone Python CLI scripts use vibe-scripts.
---

# vibe-apps：应用路线与共用边界

直接服务用户先由 [vibe-flow](../vibe-flow/SKILL.md) 判档；已分派角色按 [role-reading.md](../vibe-flow/references/role-reading.md) 的清单读公共节与本文件适用部分，沿用派工结论，不通读父入口或重判档。流程厚度、决策边界、低耦合、文档和收工 fork 归 `vibe-flow`，本 skill 只选应用路线、给共用约束；具体实现只加载选中的分支。

## 路线选择（按顺序判断）

1. **用户已明确的选择优先**：语言、框架、原生界面、浏览器访问、资源限制等已经谈定就沿用。约束相互冲突时只澄清那个冲突，不用默认栈覆盖用户选择。
2. **已有项目沿用当前路线、语言和框架**：普通修改不触发迁移。用户明确要求迁移，或已确认的目标需要迁移时，先核对行为契约与影响范围。
3. **新建应用看实际交付需求**：需要浏览器访问或网站交付 → Web；本地桌面工具、上位机、优先低内存 → 原生。仅“以后可能变网站”不强制引入 Web 栈，保留业务与界面分离即可。
4. **未指定时的默认**：新建本地桌面应用用原生 Python + ttkbootstrap；Web 路线默认 Python + FastAPI，仅桌面 Web 壳交付加 pywebview；浏览器/网站交付不用桌面壳。明确选择纯 Rust 的原生应用一律用 Slint，加载 Rust 参考，不再比较其他 Rust GUI；不因默认 Python 而回退。

| 已选路线 | 只加载这个分支 |
|---|---|
| 原生桌面 | [vibe-apps-native](../vibe-apps-native/SKILL.md) |
| Web 界面 | [vibe-apps-web](../vibe-apps-web/SKILL.md) |

直接服务用户调用分支时先遵守以上选择与共用边界；已分派角色沿用已定路线，只读角色清单要求的共用部分；不需要把另一条分支全文加载进来。独立 Python CLI 即使要打包分发，仍用 `vibe-scripts`；其他语言的无界面项目沿用其项目规范，不强加 GUI。

## 架构讨论与共用边界

新项目按 `vibe-flow` §4 先讨论架构，路线/框架选择不能代替职责与依赖讨论。结合业务复杂度、交互状态、设备/后台任务和维护成本给出推荐；简单工具可以选界面与纯逻辑分离，有业务规则、用例编排、设备或任务生命周期的应用重点考虑 **Clean 分层**。Clean 管业务分层与依赖方向，展示层怎么写另按下面的展示状态规则和框架能力选，两者不是套餐（用户 2026-10-28 定，不再默认 MVVM）。采用哪一种、具体分到什么程度，讨论谈定后再搭脚手架。

选定 Clean 分层，或改动涉及展示状态、后台结果时，读 [references/clean-mvvm.md](references/clean-mvvm.md) 对应小节，执行其中的依赖、状态和验证契约；分支骨架里的分层目录只在选定 Clean 时适用，不能反过来强制所有项目采用。既有项目普通修改沿用已定架构，包括按旧版 Clean + MVVM 起的项目（其中的 ViewModel 按展示状态理解，不改名不删）；迁移须明确职责与模块范围，纯样式/文案修改不发起迁移，不把局部符合报告成全项目符合。

- **业务规则可独立测试**：输入显式传入、结果显式返回，不读取全局路径，不依赖 GUI、设备或网络；碰 IO 的实现放适配层。
- **状态按职责归属**：领域状态在 domain；连接、会话、任务和退出流程由 application 管理；展示状态（影响界面判断的值、请求代次、在途标记）归展示层，不成为第二个业务状态源。每项状态一个权威来源，不逐控件镜像：简单的局部草稿由控件或它绑定的变量持有，参与联动、异步预演、多步流程的才放进明确的展示状态。
- **展示层按单向数据流**（所有 GUI 适用）：界面从状态投影，状态只在一处更新。简单字段和局部草稿交给框架自带绑定（Tk Variable、Slint 属性/`<=>`/global、自定义 Model）同步，不另建状态、不另写 apply；只有命中下面抽取条件的跨事件状态，才让用例结果和后台结果经一处 apply 进入展示状态。框架绑定不了的派生和没有绑定的原生 JS，由一个 render/刷新函数定义一次。业务判断不写在控件回调里，回调可以直接调用例，耗时工作交后台。只对本次改动的代码：同一换算第二次出现就抽共用纯函数；出现请求序号比对、在途标记、晚到丢弃或多步对话框，就集中到一处状态转换并测事件序列。不建 BaseViewModel、通用绑定框架、Store/Dispatcher 或 Redux 式状态库。
- **依赖向内**：domain/application 不导入 GUI 框架、具体驱动/数据库，以及本项目的展示层和 adapters；infrastructure 实现 application/domain 定义的 ports，由入口注入。纯计算可直接依赖 domain，不为层层转发造空用例。入口组装并触发生命周期，用例层执行恢复、停止和清理的业务顺序。小应用用模块表达，不要求多包或 DI 框架。
- **通信按实际边界选**：进程内可直接调用或用事件/消息交回结果；跨进程、远程或 Web 通信记录实际协议契约。HTTP 与 Web 前端不得使用专有业务桥的规则只属于 Web 分支，不要求原生应用加 HTTP、序列化层或多语言桥。
- **关窗即释放界面进程**（用户 2026-10-27 定，只管本应用自己起的桌面进程；浏览器访问/网站交付关网页不结束服务）：默认关窗就是整个进程退出，不做托盘、不留后台。用户要求关窗后继续工作的（设备监听、定时任务、给 CLI/AI 共用的服务）才拆成内核进程 + 界面进程，关窗只退出界面进程、不停业务，重开再启动界面连回内核。禁止隐藏窗口或藏到托盘而界面进程留着；内核不建普通窗口（有的机器上安全软件、输入法会往带窗口的进程注入模块，开销可达几十 MiB）。架构讨论遇到这类需求，或改已有项目的关窗/托盘/常驻行为时，读 [references/gui-lifecycle.md](references/gui-lifecycle.md)。
- **变化轴与默认配置**：沿用 `vibe-flow` §5；多实现注册表仍在实际第二个成员或调用方按成员分支时建立；隔离实际外部依赖所需的 ports 不受成员数限制，不为未来换语言预建插件框架。

## 脚手架与文档

应用独占目录，文档位置按 `vibe-flow` §6；实现者随脚手架创建根 `AGENTS.md` 的架构约束段，其他操作说明及 BLUEPRINT/CHANGELOG 由收工 fork 按 `living-blueprint` 维护。

所有路线使用同一个项目标记，标题必须原样保留；只填项目实际选择，不保留占位项：

```markdown
## 架构约束（vibe-apps）
实现选择：<已选路线、语言、GUI 框架与交付方式>。
架构：<讨论谈定的结构与选择理由；若采用 Clean 分层，列明实际依赖边界；展示状态放在哪>。
<实际模块归属、状态/线程所有者及验证方式；已有检查写命令与覆盖范围，尚无自动检查如实说明；存量迁移写明范围>。
<选中分支的项目实际约束，如主线程/后台任务、或 Web HTTP 与离线资源规则>。
```

这个标记兼容既有 Web 项目；分支名与语言不另造标记。实现细节留在 AGENTS；换语言仍需遵守的行为、数据和验收契约才进入蓝图，不把具名模块或框架调用方式写成通用硬约束。

换路线、框架、语言或多人网站交付时才读 [references/evolution.md](references/evolution.md)。

## 界面：效果图先行

只靠文字需求直接写原生界面，观感往往很差；先在浏览器里把样子定下来，再照图实现。

**何时走**：新应用、新页面、布局大改，在框架确定后、写主要界面之前。小改沿用项目已有的 DESIGN.md 和界面，不重画。流程厚度仍按 `vibe-flow` 判档。

1. **最小 DESIGN.md**：项目根放 `DESIGN.md`（沿用上游约定，别的 agent 能自己找到），只写本次用到的 token（颜色、字体、字号、间距、圆角）和一段说明层次与风格的正文；已有就复用、按需补。**格式以 `vendor/design-md/spec.md` 为准**（上游原文，这里不复述）。风格起点可从 [awesome-design-md](https://github.com/voltagent/awesome-design-md) 挑一份改。
   - **颜色名用 DaisyUI 的语义名**：`primary` `secondary` `accent` `neutral` `base-100` `base-200` `base-300` `base-content` `info` `success` `warning` `error`，以及各自的 `*-content`（放在该色上的文字色）。原生框架要的而这套没有的角色（输入框、选中行、边框、禁用等）按需补具名 token；怎么对到框架的槽位写在语言参考里，不一对一硬套。
   - `omitted` 只表示这套设计有意不定义某一整节，**不用来声明框架做不到什么**；框架能力看语言参考的能力清单。
2. **一个可切换状态的 HTML 效果图**：原生路线放 `docs/mockup/`（`index.html` 及其资源），Web 路线直接写在 `web/`。按目标窗口的逻辑像素 1:1 画（窗口多大、控件多高都按实际尺寸），实现时数值才能直接搬。
   - **按所选框架的能力清单画**（见语言参考），不画框架做不出的效果。原生路线用纯 HTML/CSS 把控件画成目标框架的样子，不用 Web 组件库——画成 Web 组件，原生就还原不了。
   - **状态按实际功能选**：正常状态，加上会改变布局或控件状态的情况（空数据、报错、长内容、运行中锁定参数；有连接功能才画断连）。同一页面里用切换按钮，不各出一份。
   - **按真实规则画**：每个状态照需求里这个状态下的规则画——需求写了“运行中参数置灰”，“运行中”那一帧就画成置灰。效果图里不出现需求没有的内容（多出一列、一种显示格式），要加就先当新需求记下来再画。用户点头的是这张图，图和需求说法不一，做出来的程序必然和他认可的样子对不上。
   - 颜色、字体、间距只引用 DESIGN.md 的值；布局结构和伸缩规则写在 HTML 里。原生路线的效果图在 `<head>` 里留一个 `<style id="design-tokens"></style>`，token 由生成器写进去（见下面「导出」），不另建 CSS 文件。
3. **用户在浏览器里改到满意**：调颜色、字体、间距体系 → 改 DESIGN.md 再重新导出；调布局、伸缩 → 改 HTML。定稿那版留在项目里，作为实现和对照的依据；改图时新增或去掉的内容同步改进需求记录。
4. **照图实现**：同时读效果图 HTML 源码（精确数值）和效果图截图（整体观感）。DESIGN.md 的值集中放进主题 / 样式一处，不在控件代码里散写色值。**第一版主要布局出来就做一次截图对照**，不等业务全部接好才发现还原不了。
5. **截图对照（AI 自己做，再交用户）**：查的是**像不像效果图**，不是“有没有重叠、截断”这类缺陷——没有缺陷的程序照样可以和效果图对不上。
   - **同尺寸、同状态、同数据**：应用窗口按效果图的尺寸截（窗口能拉伸也先恢复到设计尺寸），用与效果图相同的样例数据，每个效果图状态各截一张。效果图截图用本机 Edge / Chrome 无头模式（`--headless=new --screenshot`，另给一个临时 `--user-data-dir`，`--force-device-scale-factor` 与应用截图一致）。应用窗口怎么截见语言参考。
   - **逐项列差异清单**，三类都要过：布局（比例、密度、对齐、伸缩后的留白位置）、控件状态（可用 / 置灰 / 选中、指示灯）、显示内容（有哪些列和字段、文字、数值格式、截断标记）。比观感不比像素。
   - **每条差异只有两个去处**：修到和效果图一致；或者保留，写明原因交用户决定。不许悄悄偏离。
   - **交给用户的是并排对照图加差异清单**（把两边截图拼成一张图），不是只给程序让他自己看——单看程序，用户看不出它和认可的效果图哪里不同。
   - 截图只管观感；键盘、中文输入、断连恢复、长日志性能仍按下面的交付验证在真实窗口里走。

**导出**：两条路线都先用 designmd 查规范，`<ver>` 取 `vendor/design-md/cli-package.json` 里的 `version`，让 CLI 和存着的规范是同一版。Windows 上命令名必须用 `designmd`。**必须用 `&&` 串成一条**：DESIGN.md 有错时 lint 退出非零，后一步照样会跑出坏结果。

- **原生路线（ttk / Slint）**：用本 skill 的 `scripts/design_theme.py`，一次产出目标框架的主题文件（ttk 的 `design_tokens.py`、Slint 的 `ui/theme.slint`），并刷新效果图 `docs/mockup/index.html` 里的 `design-tokens` 块：

  ```
  npx -y -p @google/design.md@<ver> designmd lint DESIGN.md && py -3 <本 skill 目录>/scripts/design_theme.py <ttk|slint> --design DESIGN.md
  ```

  它直接读 DESIGN.md 源数据，超出支持范围的写法（ttk 用透明色、无单位尺寸、`lineHeight`、`components` 等）逐条报错、带行号，不静默丢；支持范围和参数看 `--ai-help`。产物提交进项目，主题和控件代码只引用产物里的值；`--check` 核对产物有没有落后于 DESIGN.md。token 写进 HTML 而不另建 `.css`：有的机器上透明加密软件会加密写出的 `.css`，浏览器读到密文，效果图就丢了全部样式。
- **Web 路线**：用 designmd 导出，整条成功后再把 `.tmp` 改名覆盖目标；失败就修 DESIGN.md，旧文件不动：

  ```
  npx -y -p @google/design.md@<ver> designmd lint DESIGN.md && npx -y -p @google/design.md@<ver> designmd export DESIGN.md --format css-vars > <目标>.tmp
  ```

  页面引导出的 `theme.css`，不手写第二份色值。**导出不是无损转换**（0.4.0 实测）：css-vars 只有颜色、间距、圆角，没有字体，无单位的 spacing 会被静默丢掉；`--format dtcg` 带字体但丢无单位的 `lineHeight`；两种都不导 `components`。导不出的值在用到的地方按 DESIGN.md 写一处，不许悄悄丢掉。

上游规范更新时跑 `py -3 <本 skill 目录>/scripts/sync_upstream.py`（在哪个目录跑都行；`--check` 只看有没有更新、不写文件），规范和 CLI 版本一起刷新，本文不用改。

## 资源与交付验证

按已选架构和本次改动规模验证。采用 Clean 分层或抽出了展示状态转换时遵守 [验证要求](references/clean-mvvm.md#验证要求)：既有小改复用检查，不为小改新建测试框架；新项目或明确的边界迁移落实约定的检查方式，说明自动覆盖与人工核对范围。架构检查不能替代真实界面测试。

所有应用按 `vibe-flow` §8 走真实入口与核心用户路径；分发应用要运行交付产物，源码能跑不代表打包产物完整。界面观感按上面「界面：效果图先行」走，流程厚度仍按本次改动判档。

**用户提了内存 / CPU 要求时**，在目标机器上拿实际应用、实际负载测，别凭语言或框架名推断省不省；怎么测读 [references/resource-check.md](references/resource-check.md)。已经达标就不重新选框架，没达标先找瓶颈再决定优化还是迁移。
