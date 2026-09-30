---
name: living-blueprint
description: How to write a personal script's or app's docs — BLUEPRINT.md (always-current "what it does", no implementation, so AI can refactor from intent), CHANGELOG.md (append-only "why it changed": the trigger, root cause, what it became, and the rejected paths), AGENTS.md (auto-loaded entry: reading order, commands, pitfalls) and docs/HANDOFF.md (progress snapshot that exists only while work is unfinished). Load it INSIDE the doc-keeping fork that vibe-flow §8 dispatches when a batch of changes is done — that fork inherits the conversation and writes the docs; the main agent doing the implementation does NOT load this skill and does not touch docs while working. Also load it when the user explicitly asks to write or restructure these docs, or when no context-inheriting subagent is available. 工具活蓝图 BLUEPRINT.md + 变更记录 CHANGELOG.md、只讲功能不讲实现、覆盖式当前全貌、记录为什么变更、交接给新会话或别的 AI、HANDOFF 进度快照、AGENTS.md 入口、重构不被旧实现绑架；由收工时派出的 fork 加载执行，干活的主 agent 不加载。微脚本用头部契约行代替,不建。≠ UI 设计系统 DESIGN.md。Stack-independent.
---

# living-blueprint：活蓝图、变更记录与交接

四份文件各管一件，不重叠：

| 文件 | 管什么 | 写法 |
|---|---|---|
| `BLUEPRINT.md` | 现在是什么 | 覆盖式，永远是当前真相；只讲功能不讲实现 |
| `CHANGELOG.md` | 怎么变成这样、为什么、丢掉了什么 | 只追加，新条目插顶部 |
| `AGENTS.md` | 怎么在这干活、先读什么 | 只写不常变的；会话启动唯一自动加载的入口 |
| `HANDOFF.md` | 现在做到哪了 | 只在有没做完的活时存在，覆盖式，做完删掉 |

代码改了哪几行归 git，四份都不重复它。**哪些项目要哪些文件、放哪，见 `vibe-flow` §6**；本 skill 管每份写什么、什么时候改。**建文件或调整某份的结构时，读 `references/templates.md` 拿模板。**

## 谁来写：收工时派出的 fork

读到这里的你，多半就是那个 fork：主 agent 干完一批活，按 `vibe-flow` §8 把文档交给你。你继承了整段对话，所以意图直接从对话里取——用户要什么、为什么改、原话怎么说、哪些路被否了——不需要主 agent 另写简报。

- **只写这几份文档**：本项目按 §6 该有的那几份（`BLUEPRINT` / `CHANGELOG` / `AGENTS.md` / `HANDOFF`，旁挂布局就是旁挂的那几份）。写入方式不限（本机若有透明加密，照环境规矩走 Python 等白名单进程写），但不改代码、不生成别的文件、不跑有其他副作用的命令；主 agent 回来会比对代码有没有被动过。
- **覆盖到这批改动的最终状态**：以磁盘上的当前代码为准，对话里中途被推翻的方案不写进蓝图（进 CHANGELOG 的「没选的路」）。
- **判断该改哪份**按下面「什么时候改」的三种情形；一份都不用改就不改，别为了留痕写假条目。
- **汇报不超过三行**：改了哪些文件，或为什么这批不用记。拿不准的意图写进汇报让主 agent 补一句，不要猜着写。
- 对话被压缩过、意图看不全时，以代码和现有文档为准。

没有能继承上下文的子 agent 时（别的平台或环境），主 agent 自己按本 skill 改，规矩相同。

## BLUEPRINT.md：只讲功能，不讲实现

**地基判据（一行该不该进蓝图）**：蓝图是**黑盒验收规格**——两份不同语言 / 框架的实现，都符合蓝图才算「同一个工具」。问：**「换一种语言从头重写，这条它必须照做才算同一个工具吗？」** 必须照做 → 进蓝图（行为契约 / I/O 契约 / 硬约束）；只是当前实现碰巧这么组织 → 不进（归 AGENTS.md / spec）。所以内部算法、数据结构、用了什么库、`core/api/web` 这类语言特定的具名分层都不进；换语言仍成立的架构原则（逻辑与 UI 解耦、变化轴的验收句）要进。用到 AI 宿主能力的项目，平台约定（模板第 6 节）过同一判据，问的是「换一个平台重写，这条必须照做吗」：时机、行为、降级和支持状态进蓝图；只属适配映射的平台事件名、字段、壳的位置和内部命令不进，归 AGENTS.md；属于对外 I/O 契约的名称照原样保留。

**两条承重设计**（做不到，蓝图就防不住「被旧实现绑架」）：

1. **行为契约**：功能一律写成「给它 X → 它做 Y / 你看到 Z」的可观察行为，外加 I/O 契约（输入输出格式、文件格式、接口字段）。漏了 I/O 契约，换语言重写就对不齐。
2. **硬约束 / 自由声明分离**：列出少数必须守的，再补一句「其余皆实现细节，可自由改」。这句**主动授权** AI 丢掉旧实现——不写，再功能向的文档 AI 也默认沿用旧结构。

**覆盖式**：正文永远是当前真相，旧描述被推翻就直接改写、不留历史（历史归 CHANGELOG）。只写已经落地的行为，做了一半的归 HANDOFF。提炼意图与行为，不逐字抄对话、不记实现过程。标准级脚本的蓝图一屏以内。

## CHANGELOG.md：只追加，专讲为什么

蓝图是覆盖式的，删掉的功能会从蓝图里消失；「试过、为什么撤了」只能靠它留下来，否则下次重构 AI 会把否掉的方案当新点子再加回来。

- **记不记，判据只有一条：用户感觉得到吗？** 记：可观察行为变了；修了用户碰到过的 bug；改了用户嫌弃的体验；出生那一条（为什么要做它，引原始需求）。不记：用户从没感知过的内部问题、纯重构、改格式——交给 git。
- **「为什么」是主体**：起因、根因写透；「改成」只写行为，不写代码怎么改。一条十行左右。
- **起因引用户原话**，别转述——原话才是真实原因，转述会失真、会往好听了写。只引和这次相关的最小片段；仓库要公开的，客户名、路径、凭据一律脱敏。
- **「没选的路」必填**，没有也写「无」：AI 重构时最容易犯的错，就是把当初否掉的方案当新点子提出来。其余行没内容就省略。
- **新条目插顶部；旧条目不改写**。后来发现判断错了，就在顶部新写一条说明推翻了哪条、为什么——被推翻的过程本身就是要留的历史。
- 不挂 commit 号：同一次提交里写的条目拿不到自己的 hash，要找提交用 `git log` / `git blame`。

## AGENTS.md：交接入口

会话启动只自动加载它，新会话不会自己去找蓝图，所以**第一段必须是阅读顺序**。之后是命令、坑，以及**搜不出来的约定**（比如「加一种格式去哪张表」、跨目录的入口关系，几行就够）；分支 skill 的架构约束段也写这里（如 `vibe-apps` 那段）。不写完整代码地图——目录树和符号 AI 用搜索、LSP 现查，写下来只会过时，还要每次跟着改。不写功能（归蓝图）、不写进度（归 HANDOFF）、不写历史（归 CHANGELOG）。命令、坑、约定变了就改它。它每个会话都会整份加载，保持一屏以内。

项目级只建 AGENTS.md，两个平台读同一份。只有当前环境的 Claude Code 确实不读 AGENTS.md 时，才加一个内容只有一行 `@AGENTS.md` 的 CLAUDE.md，别把正文复制进去。

## HANDOFF.md：进度快照

- **什么时候写**：活没做完就要结束会话、要交给别的 AI、或用户说「先到这」时，当轮建立或覆盖。
- **做完就删**：整件事收尾时，成果进蓝图和 CHANGELOG，删掉 HANDOFF。它只描述此刻，不许长成第二份 CHANGELOG。
- **写给零上下文的人**：接手的可能是另一个 AI，没看过这次对话。路径写全、状态写实（「改了没提交」「测试红着」），别写「按刚才说的做」。

## 什么时候读、什么时候改

- **读**（主 agent）：新会话上手时，按 AGENTS.md 第一段先看 `HANDOFF.md`（如有）。要动哪块，读 `BLUEPRINT.md` 里那块的行为契约，再搜 `CHANGELOG.md` 里那块相关的「没选的路」；整体重构才通读蓝图。CHANGELOG 不默认翻最近几条，也不通读。
- **建**：工具出生（第一次交付）时蓝图和 CHANGELOG 一起建，CHANGELOG 第一条记为什么要做它。
- **改**：每批改动做完、交付之前，由 fork 改（见上文「谁来写」），不等用户说「更新蓝图」。「必须带两份」指两份始终存在，不是每批都要有改动：
  - 功能、I/O 契约或硬约束变了 → 蓝图覆盖对应小节，CHANGELOG 加一条；
  - 修了用户碰到过的 bug、改了用户嫌弃的体验，蓝图本来就写着正确预期 → 只在 CHANGELOG 加一条；
  - 纯内部重构、用户没感知过的问题 → 交给 git，都不动。

### fork 怎么写：三源、三条死命令

fork 和主 agent 一样泡过实现细节，最容易犯的错是把 how 写进蓝图。

- **三源并用**：现有 `BLUEPRINT.md`（基底）＋ 继承来的对话（意图源：用户想要什么、为什么——代码常表达不出意图，且可能正是要被重构掉的旧实现）＋ 当前代码（现实源：哪些意图真落地了）。
- **三条死命令**：① 只写可观察行为与 I/O 契约，不写实现；② 只收最终拍板的意图，弃掉对话中途被否的废案；③ 覆盖式对账，标出「意图 ≠ 当前代码」处（那是下次重构的缺口）。
- 小改也一样交给 fork，主 agent 不 inline：省下的是主 agent 的上下文，不是这几行字。

## 与邻居划界

| 对象 | 本 skill 的不同 |
|---|---|
| spec / plan（如 `superpowers-manual` 的 dated spec/plan） | 它们记每次改动「怎么做」；蓝图只留「当前是什么」，一处 what 一处 how。本 skill 不依赖那套流程 |
| ADR | 蓝图不记历史；历史归 CHANGELOG，且只记用户感觉得到的变化，不是每个架构决策都记 |
| DESIGN.md（UI 设计系统） | 那是视觉规范；这是功能架构，所以文件叫 BLUEPRINT.md |
| `NEEDS.md`（`clarify-needs`） | 那是人读的「你的哪些需求做了没做」；蓝图是「工具现在是什么」 |

## 致谢

固定骨架与「what/why 非 how-to-work」定位借鉴 ceaksan/living-architecture；「功能写成可验证行为」框法借鉴 Spec-Driven Development（spec-kit/OpenSpec）。均为思路借鉴，未复制代码。
