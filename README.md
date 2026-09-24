# vibe-flow

一套完整但不重的个人 vibe-coding 工作流。承重的只有一个显式档位：**小事要省，大事要好。**

省的是流程，不是质量；好的是该厚的地方厚，不是每次走满。重流程框架的病不在「太严谨」，
在于只有一档，所有事一律走满。

## 装

```
/plugin marketplace add patrick1099/vibe-flow
/plugin install vibe-flow@vibe-flow
```

入口是 `vibe-flow`。它判一次档，澄清厚度、探不探方案、叫不叫另一个 AI 审、验证强度、收工后要不要
回头，全是这一次判定的下游。要不要留文档不归档位管，看工具寿命（见下「两条不分档的底线」）。

## 判档判的是什么

```
「帮我写个脚本把串口日志转成 csv」
  → 省档。不澄清、最小可用,写完拿代表性输入跑一遍;不到 100 行的微脚本只写头部说明,不另建文档

「我要做个抓包分析工具,做完发给同事用」
  → 好档。命中「范围大」→ 先挖需求分清偏好与约束、技术方案 AI 定并交 codex 审、
    落 NEEDS.md;因为要给别人,还要打包后实际用一遍再交

「这个抓包工具导出时列名改一下」(工具已经用了半年)
  → 省档。明确的小改,直接改、跑一遍、把 CHANGELOG 记上
```

判档只看**这次改动**，命中任一即好档：

- 范围或影响面大：新加一整块功能、要新建的工具本身就复杂；或改动虽小但一错就影响全部数据（单位换算、统计口径）。
  「新建」本身不算——需求清楚的小脚本，新写也是省档
- 出错后果重 / 不可逆：删除 / 覆盖 / 迁移数据、联网上传、发出去收不回
- 关键未知：有会实质改变行为、数据或方案的未知
- 多目标纠缠：两个以上独立目标或用户

工具要用多久、给不给别人，**不影响这次走多厚**，只影响要不要留文档、要不要按交付形态验证。
一个长期工具上的明确小改就是小事。

默认省档，升到好档必须说得出理由。你一句话可以直接定档，优先于以上判据：「这个随便做一下」
→ 省档；「这个要做好」→ 好档。

## 七个 skill

| skill | 环节 | 触发 | 是否改文件 |
|---|---|---|---|
| `vibe-flow` | 总入口：判意图 → 判档 → 路由 → 决策边界 → 验证收尾 | 建/改/扩一个脚本、工具、应用、功能 | 只改你要它改的 |
| `clarify-needs` | 明确需求：把目标 / 方案 / 偏好 / 约束分开 | 手动，或需求不清的大活（新项目、新一整块功能）动手前自触发 | 写 `docs/NEEDS.md` |
| `living-blueprint` | 留意图与交接：当前全貌 ＋ 为什么变更 ＋ 交接入口 ＋ 进度快照 | 微脚本以外的脚本 / 应用必带，出生时建、行为变了同一轮更新 | 写 `BLUEPRINT.md` ＋ `CHANGELOG.md`（＋`AGENTS.md`、按需 `HANDOFF.md`） |
| `vibe-scripts` | 实现：独立 Python 脚本的四层五区 + 分级 | 写/改独立脚本前 | 写脚本 |
| `vibe-apps` | 实现：带界面 / 要分发的 Python 应用五层 | 搭应用脚手架前 | 写应用 |
| `cut-scope` | 回头剪枝：冷眼核对真实需求 vs 已膨胀的设计 | 手动，迭代多轮后 | 只读，只给方向 |
| `scan-field` | 对外扫同款两头：开工前查市面有没有 / 完工后产原创度对比 | 手动，或由 vibe-flow 路由 | 只产结论 |

`clarify-needs` 会自触发但带闸，只在这次要做的事够大、需求本身又不清时起（开新项目 / 新工具、
新加一整块功能、多目标纠缠、需求越聊越多），明确的小改 / 改 bug / 纯问答不起。闸写在 description 里，是软约束；
误伤了说一句「这个随便做一下」就跳过。`cut-scope` / `scan-field` 两个回头类 skill 是约定式手动。

要做的东西有流程时，`clarify-needs` 会把「它跑起来是什么样」画成图：用 [D2](https://d2lang.com)
写，`skills/clarify-needs/scripts/model_page.py` 渲染成本地网页自动打开，猜的地方标黄色虚线
框，页面底下列出要你拍板的问题。讲内部怎么搭的实现图默认不画，你想看才画；分层架构那种靠格子对
齐的图（APP / Driver / HAL / BSP）D2 摆不出来，改写 HTML 片段交给同一个脚本出页面。本机没装
`d2` 时流程图退回对话里的 ASCII 图。

## 两条不分档的底线

**低耦合，变化轴可插拔。** 逻辑和 IO / 界面分开，微脚本也一样。以后会增、删、换的那类东西
（平台、格式、厂商、数据源）叫变化轴：一个成员时代码聚在一处，第二个出现时收成一张注册表，
加或去掉一个成员只动它自己和注册表。成员各自依赖外部东西（第三方库、设备、网络）时，再做到
一个坏了不拖垮其他。细则以入口 `vibe-flow` §5 为准。

**两份文档。** 微脚本以外的脚本和应用都带 `BLUEPRINT.md`（现在是什么）和 `CHANGELOG.md`
（为什么变成这样：起因引用户原话、根因、改成什么、没选的路）。按目录归属放：独占一个目录的放
`docs/` 并带 `AGENTS.md`，和别的脚本共处的用同名旁挂文件。什么时候改哪份见 `living-blueprint`，
哪些项目要哪些文件以入口 `vibe-flow` §6 为准。代码改了哪几行交给 git。

这一条有闸，Claude Code 和 Codex 都能用。Claude Code 的 Stop hook（`hooks/doc_gate.py`）从
本轮记录里找成功的 Write / Edit；Codex 入口（`hooks/doc_gate_codex.py`）用 PostToolUse 收集本轮
成功的 `apply_patch` 文件，在 Stop 时检查。两边共用 `doc_gate.py` 的项目识别、文档位置判定和提醒，
缺文档或两份都没动时只拦一次，让 AI 说清「行为变了没有、要不要记」，回应后放行。判断仍归 AI，
免得为过闸写假条目。

认不认得出是 vibe 项目靠三种标记：`docs/BLUEPRINT.md`、脚本头部 `结构: vibe-scripts/standard`
或 `toolkit`、AGENTS.md（或旧项目的 CLAUDE.md）里的「架构约束（vibe-apps）」段；没有标记的仓库
（比如公司代码）一律不管。文档该放哪先看已有布局（旁挂文件、`docs/`、`AGENTS.md`），看不出来就
把两个位置都列出来，不猜。

Codex 的配置随插件分发：`.codex-plugin/plugin.json` 指向 `hooks/codex.json`，不用改用户的全局
`config.toml`。新装或钩子定义变化后，须先在 Codex 中审阅并信任钩子（CLI 用 `/hooks`）；未信任、
hooks 功能被关闭或管理员禁用插件钩子时不会执行。当前在桌面引擎 `0.155.0-alpha.16.3` 验证。
机制和分发规则见 [Codex Hooks](https://learn.chatgpt.com/docs/hooks) 与
[插件钩子文档](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks)。

Codex 只在插件数据目录暂存文件路径，按会话、回合和工具调用隔离，Stop 或 Interrupt 后清理本轮记录；
不读取会话日志，也不把用户原有的 git 改动算成本轮修改。边界：两边都不识别经 shell / Python 脚本
落盘的改动；Codex 也不收集其他 MCP 写文件工具。子代理的改动不汇总到主会话，本闸只在主会话 Stop
检查。闸内部出错时提示错误并放行。

回归测试：`py -3 -m unittest discover -s tests -v`。

## 交接

新开会话接着做、换别的 AI 接手，光有蓝图不够：蓝图只讲「是什么」，不讲「怎么在这干活」和
「做到哪了」，而且新会话只自动加载 AGENTS.md，不会自己去找蓝图。所以再加两份：

- `AGENTS.md`（有自己目录的项目，放根目录）：交接入口。第一段写阅读顺序（HANDOFF → BLUEPRINT →
  CHANGELOG），然后是跑 / 测 / 打包命令、代码地图、项目特有的坑。项目级只建它，两个平台读同一份。
- `docs/HANDOFF.md`：进度快照，只在有没做完的活时存在，覆盖式、一屏以内——在做什么、做了一半的
  卡在哪、下一步、等你拍板的、别碰的。活没做完就结束会话时建立或更新；整件事做完就删掉。

四份各管一件：AGENTS 管怎么干活，HANDOFF 管做到哪，BLUEPRINT 管是什么，CHANGELOG 管为什么。

Claude Code 默认只读 CLAUDE.md。想让它读项目的 AGENTS.md，要么启用内置的 agents-md 并把
`instructionFiles` 设成 `claude-md-and-agents-md`，要么在项目里放一个只有一行 `@AGENTS.md` 的
CLAUDE.md。Codex 原生读 AGENTS.md。

## 环节与档位对照

| 环节 | 省档（默认） | 好档 |
|---|---|---|
| 开工前 | 查自己有没有现成的 | ＋查市面有没有（`scan-field` 开口那头） |
| 明确需求 | 不澄清，或只问一个问题 | 挖目标 / 分清偏好与约束 / 翻译验收；有流程的画「它跑起来是什么样」图 |
| 探方案 | 不探，直接做 | 技术取舍 AI 定、codex 审；影响你用起来的翻译成后果再问你；界面类出原型让你挑；定稿后三行白话告知方向就开工 |
| 实现 | 最小可用；守低耦合底线，不预建插口 | 按分支的完整纪律；三点设计里列变化轴 |
| 留文档 | 按工具寿命不按档：微脚本头部契约行；其余 `BLUEPRINT.md` ＋ `CHANGELOG.md`；有目录的＋`AGENTS.md`；有没做完的活＋`HANDOFF.md` | 同左；需求仍演化时＋`NEEDS.md` |
| 验证 | 代表性输入跑通 ＋ 拔插自查；给别人的按交付形态跑 | 按交付形态实际使用 ＋ 针对性测试 ＋ 结构测试 |
| 收工后 | 无 | 膨胀了剪枝 / 完工了扫同款 |

分工：需求我们一起定；技术方案 AI 出、另一个 AI（codex）挑毛病、AI 拍板；只有「选 A 和选 B 你用起来
会不会不一样」的点才回到你这里，而且先翻译成后果（快慢、能不能离线、会不会动你的数据、多花多少时间），
不讲技术名词。方案定了用三行白话告诉你（做什么 / 你会看到什么 / 不做什么）然后直接开工，方向不对你随时叫停；
已经确认过的方向不会再让你点一次头，只有冒出新的、影响你使用的选择才停下来问。

不命中的环节完全不提。这是路由图，不是阶段清单：把它当必经阶段依次跑，就退回了它要取代的
那种流程。

## 与重流程框架的关系

skill 之间不自动串联，自动钩子只用于上面那道文档闸。需要正式 spec/plan 落盘再按计划执行、TDD、工作树、并行子
代理这类重仪式时，手动去调 [superpowers-manual](https://github.com/patrick1099/superpowers-manual)。
本工作流不依赖它，没装也能走完全程。

插件同时支持 Claude Code 和 Codex，只有入口 skill 带 `agents/openai.yaml`。两端的文档闸分别接入
各自的 hook 事件，共用一份判定逻辑；Codex 需使用支持插件钩子的版本并完成钩子信任，`vibe-flow` §8
说明被拦后如何判断。

## 沿革

本插件由两个前身合并而成（2026-07-30）：`vibe-flow` / `vibe-scripts` / `vibe-apps` 原在
[xu-skills](https://github.com/patrick1099/xu-skills)，`clarify-needs` / `living-blueprint` /
`cut-scope` / `scan-field` 原是 [true-north](https://github.com/patrick1099/true-north) 四件套。

v0.4.0 之前 `clarify-needs` 标着 `disable-model-invocation: true`，是硬手动，模型根本拉不
起来。实际用下来这条闸太死：真正需要它的项目场景也一次都进不去，全靠人记得敲。改成自触发
加 description 限流。

合并理由与档位设计见 `docs/history/2026-07-30-vibe-flow-plugin-merge.md`，更早的设计记录见
`docs/history/` 其余文件，`clarify-needs` 的 RED 基线与夹具见 `docs/evals/`。
