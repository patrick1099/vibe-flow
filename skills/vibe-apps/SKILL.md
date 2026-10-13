---
name: vibe-apps
description: Route personal GUI apps to native desktop or Web UI before scaffolding, and apply shared application boundaries and delivery checks. GUI、上位机、桌面工具、Web 界面、打包应用；支持用户明确选择 Python 或纯 Rust。Load after vibe-flow; standalone Python CLI scripts use vibe-scripts.
---

# vibe-apps：应用路线与共用边界

先由 `vibe-flow` 判档。流程厚度、决策边界、低耦合、文档和收工 fork 归 `vibe-flow`，本 skill 只选应用路线、给共用约束；具体实现只加载选中的分支。

## 路线选择（按顺序判断）

1. **用户已明确的选择优先**：语言、框架、原生界面、浏览器访问、资源限制等已经谈定就沿用。约束相互冲突时只澄清那个冲突，不用默认栈覆盖用户选择。
2. **已有项目沿用当前路线、语言和框架**：普通修改不触发迁移。用户明确要求迁移，或已确认的目标需要迁移时，先核对行为契约与影响范围。
3. **新建应用看实际交付需求**：需要浏览器访问或网站交付 → Web；本地桌面工具、上位机、优先低内存 → 原生。仅“以后可能变网站”不强制引入 Web 栈，保留业务与界面分离即可。
4. **未指定时的默认**：新建本地桌面应用用原生 Python + ttkbootstrap；Web 路线默认 Python + FastAPI，仅桌面 Web 壳交付加 pywebview；浏览器/网站交付不用桌面壳。明确选择纯 Rust 的原生应用加载 Rust 参考，按实际界面需求验证框架；不因默认 Python 而回退。

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

## 资源与交付验证

所有应用按 `vibe-flow` §8 走真实入口与核心用户路径；分发应用要运行交付产物，源码能跑不代表打包产物完整。界面选择涉及观感时给原型，流程厚度仍按本次改动判档。

**用户提了内存 / CPU 要求时**，在目标机器上拿实际应用、实际负载测，别凭语言或框架名推断省不省；怎么测读 [references/resource-check.md](references/resource-check.md)。已经达标就不重新选框架，没达标先找瓶颈再决定优化还是迁移。
