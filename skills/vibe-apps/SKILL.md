---
name: vibe-apps
description: Route personal GUI apps to native desktop or Web UI before scaffolding, and apply shared application boundaries, the mockup-first UI flow (DESIGN.md + HTML mockup + screenshot comparison) and delivery checks. GUI、上位机、桌面工具、Web 界面、打包应用、界面效果图、DESIGN.md、照图实现；支持用户明确选择 Python 或纯 Rust（Slint）。Load after vibe-flow; standalone Python CLI scripts use vibe-scripts.
---

# vibe-apps：应用路线与共用边界

先由 `vibe-flow` 判档。流程厚度、决策边界、低耦合、文档和收工 fork 归 `vibe-flow`，本 skill 只选应用路线、给共用约束；具体实现只加载选中的分支。

## 路线选择（按顺序判断）

1. **用户已明确的选择优先**：语言、框架、原生界面、浏览器访问、资源限制等已经谈定就沿用。约束相互冲突时只澄清那个冲突，不用默认栈覆盖用户选择。
2. **已有项目沿用当前路线、语言和框架**：普通修改不触发迁移。用户明确要求迁移，或已确认的目标需要迁移时，先核对行为契约与影响范围。
3. **新建应用看实际交付需求**：需要浏览器访问或网站交付 → Web；本地桌面工具、上位机、优先低内存 → 原生。仅“以后可能变网站”不强制引入 Web 栈，保留业务与界面分离即可。
4. **未指定时的默认**：新建本地桌面应用用原生 Python + ttkbootstrap；Web 路线默认 Python + FastAPI，仅桌面 Web 壳交付加 pywebview；浏览器/网站交付不用桌面壳。明确选择纯 Rust 的原生应用一律用 Slint，加载 Rust 参考，不再比较其他 Rust GUI；不因默认 Python 而回退。

| 已选路线 | 只加载这个分支 |
|---|---|
| 原生桌面 | [vibe-apps-native](../vibe-apps-native/SKILL.md) |
| Web 界面 | [vibe-apps-web](../vibe-apps-web/SKILL.md) |

直接调用分支时也先遵守以上选择与共用边界；不需要把另一条分支全文加载进来。独立 Python CLI 即使要打包分发，仍用 `vibe-scripts`；其他语言的无界面项目沿用其项目规范，不强加 GUI。

## 共用边界

- **业务规则可独立测试**：输入显式传入、结果显式返回，不读取全局路径，不依赖 GUI、设备或网络；碰 IO 的实现放适配层。
- **应用状态与纯规则分开**：连接、会话、任务和 UI 状态可以由应用层或界面层拥有。规则不依赖“当前窗口/当前用户”的全局对象；不为未来用途预建多用户、trait 或接口体系。
- **依赖单向**：界面与适配器通过应用层调用业务规则；规则不知道界面存在。入口只负责配置、依赖组装与资源生命周期。小应用用几个模块表达这些职责即可，不要求一职责编一个包。
- **通信按实际边界选**：进程内可直接调用或用事件/消息交回结果；跨进程、远程或 Web 通信记录实际协议契约。HTTP 与 Web 前端不得使用专有业务桥的规则只属于 Web 分支，不要求原生应用加 HTTP、序列化层或多语言桥。
- **变化轴与默认配置**：沿用 `vibe-flow` §5；只有出现实际的第二个成员或调用方按成员分支时才收口，不为未来换语言预建插件框架。

## 脚手架与文档

应用独占目录，文档位置按 `vibe-flow` §6；实现者随脚手架创建根 `AGENTS.md` 的架构约束段，其他操作说明及 BLUEPRINT/CHANGELOG 由收工 fork 按 `living-blueprint` 维护。

所有路线使用同一个项目标记，标题必须原样保留；只填项目实际选择，不保留占位项：

```markdown
## 架构约束（vibe-apps）
实现选择：<已选路线、语言、GUI 框架与交付方式>。
业务规则与 UI/IO 分离，可独立测试；应用状态由明确的所有者维护。
<选中分支的项目实际约束，如主线程/后台任务、或 Web HTTP 与离线资源规则>。
```

这个标记兼容既有 Web 项目；分支名与语言不另造标记。实现细节留在 AGENTS；换语言仍需遵守的行为、数据和验收契约才进入蓝图，不把具名五层或框架调用方式写成通用硬约束。

换路线、框架、语言或多人网站交付时才读 [references/evolution.md](references/evolution.md)。

## 界面：效果图先行

只靠文字需求直接写原生界面，观感往往很差；先在浏览器里把样子定下来，再照图实现。

**何时走**：新应用、新页面、布局大改，在框架确定后、写主要界面之前。小改沿用项目已有的 DESIGN.md 和界面，不重画。流程厚度仍按 `vibe-flow` 判档。

1. **最小 DESIGN.md**：项目根放 `DESIGN.md`（沿用上游约定，别的 agent 能自己找到），只写本次用到的 token（颜色、字体、字号、间距、圆角）和一段说明层次与风格的正文；已有就复用、按需补。**格式以 `vendor/design-md/spec.md` 为准**（上游原文，这里不复述）。风格起点可从 [awesome-design-md](https://github.com/voltagent/awesome-design-md) 挑一份改。
   - **颜色名用 DaisyUI 的语义名**：`primary` `secondary` `accent` `neutral` `base-100` `base-200` `base-300` `base-content` `info` `success` `warning` `error`，以及各自的 `*-content`（放在该色上的文字色）。原生框架要的而这套没有的角色（输入框、选中行、边框、禁用等）按需补具名 token；怎么对到框架的槽位写在语言参考里，不一对一硬套。
   - `omitted` 只表示这套设计有意不定义某一整节，**不用来声明框架做不到什么**；框架能力看语言参考的能力清单。
2. **一个可切换状态的 HTML 效果图**：原生路线放 `docs/mockup/`（`index.html` 及其资源），Web 路线直接写在 `web/`。按目标窗口的逻辑像素 1:1 画（窗口多大、控件多高都按实际尺寸），实现时数值才能直接搬。
   - **按所选框架的能力清单画**（见语言参考），不画框架做不出的效果。原生路线用纯 HTML/CSS 把控件画成目标框架的样子，不用 Web 组件库——画成 Web 组件，原生就还原不了。
   - **状态按实际功能选**：正常状态，加上会改变布局的边界情况（空数据、报错、长内容；有连接功能才画断连）。同一页面里用切换按钮，不各出一份。
   - 颜色、字体、间距只引用 DESIGN.md 的值；布局结构和伸缩规则写在 HTML 里。
3. **用户在浏览器里改到满意**：调颜色、字体、间距体系 → 改 DESIGN.md 再重新导出；调布局、伸缩 → 改 HTML。定稿那版留在项目里，作为实现和对照的依据。
4. **照图实现**：同时读效果图 HTML 源码（精确数值）和效果图截图（整体观感）。DESIGN.md 的值集中放进主题 / 样式一处，不在控件代码里散写色值。**第一版主要布局出来就做一次截图对照**，不等业务全部接好才发现还原不了。
5. **截图对照（AI 自己做，再交用户）**：固定窗口尺寸与样例数据，截应用窗口，与效果图同一状态并排看；效果图截图用本机 Edge / Chrome 的无头模式（`--headless --screenshot`，窗口尺寸与应用客户区一致，缩放比与系统一致）。逐项看布局比例、信息密度、字号层级、对齐、裁切、状态辨识，列出差异并修正，修完再请用户过目。比观感不比像素。应用窗口怎么截见语言参考。截图只管观感；键盘、中文输入、断连恢复、长日志性能仍按下面的交付验证在真实窗口里走。

**导出**：`<ver>` 取 `vendor/design-md/cli-package.json` 里的 `version`，让 CLI 和存着的规范是同一版：

```
npx -y -p @google/design.md@<ver> designmd lint DESIGN.md && npx -y -p @google/design.md@<ver> designmd export DESIGN.md --format css-vars > <目标>.tmp
```

**必须用 `&&` 串成一条**：DESIGN.md 有错时 lint 退出非零，而 export 照样退出 0、会导出坏结果。整条成功后再把 `.tmp` 改名覆盖目标；失败就修 DESIGN.md，旧文件不动。Windows 上命令名必须用 `designmd`。效果图引导出的 `theme.css`，不手写第二份色值。

**导出不是无损转换**（0.4.0 实测）：css-vars 只有颜色、间距、圆角，没有字体；`--format dtcg` 带字体但丢无单位的 `lineHeight`；两种都不导 `components`。导不出的值在用到的地方按 DESIGN.md 写一处，不许悄悄丢掉。原生主题目前由 AI 按 DESIGN.md 手工搬进主题文件一处，不经 node。

上游规范更新时跑 `py -3 <本 skill 目录>/scripts/sync_upstream.py`（在哪个目录跑都行；`--check` 只看有没有更新、不写文件），规范和 CLI 版本一起刷新，本文不用改。

## 资源与交付验证

所有应用按 `vibe-flow` §8 走真实入口与核心用户路径；分发应用要运行交付产物，源码能跑不代表打包产物完整。界面观感按上面「界面：效果图先行」走，流程厚度仍按本次改动判档。

**用户提了内存 / CPU 要求时**，在目标机器上拿实际应用、实际负载测，别凭语言或框架名推断省不省；怎么测读 [references/resource-check.md](references/resource-check.md)。已经达标就不重新选框架，没达标先找瓶颈再决定优化还是迁移。
