---
name: supervisor
description: "Batch supervisor mode for a personal project: the main session stops implementing and hands an agreed multi-task plan to ONE supervisor sub-agent, which dispatches short worker tasks, handles ordinary failures, verifies and finishes the docs; the main session only gets ≤8-line briefs and real user decisions. Use ONLY when the user explicitly names this mode — 你当监工 / 让子 agent 当监工派活 / 用监工模式做 / 批次监工 / 主会话别自己干、交给监工 / /vibe-flow:supervisor / $supervisor. Do NOT self-invoke for ordinary multi-step work, for a plain 派个子 agent 去做 (that is ai-room), for splitting work into steps, or when the user is discussing or reviewing this skill itself. 公司固件不用。"
---

# supervisor：批次监工（只在你点名时用）

## 什么时候用

- **只在用户明确要监工模式时。** 没点名不进；`vibe-flow` 也不主动推荐它。单说“派活 / 多 agent 分工 / 派个子 agent”不算：一次性委派走 `ai-room`，平时的执行与外援按 vibe-flow 的 collaboration.md。
- **只用于个人项目。** 批次状态保存在项目的 `HANDOFF.md` 里，公司固件 / 产品仓不建 vibe 文档，被叫到那里就直说用不了。
- **小活只提一句成本。** 只有一两步短活时说一句“这件直接做更省”，随后照点名的监工模式继续，不停下等确认，也不要求他证明值得。

用户点名本身就是走三层的授权，不再问要不要；其余授权（改、提交、发布）照原计划，不因进入监工模式扩大。

## 两个目录（派工提示里都写绝对路径）

| 占位 | 指什么 | 里面用到的 |
|---|---|---|
| `<supervisor目录>` | 本 skill 目录 | [references/supervisor.md](references/supervisor.md)（监工执行与状态工具）、`scripts/batch_state.py`、`vendor/` |
| `<vibe-flow目录>` | 同插件的 `skills/vibe-flow` | `SKILL.md`（公共闸）、`references/role-reading.md`、`references/collaboration.md`、`references/doc-fork.md` |

## 主会话：启动与交接

不改变 vibe-flow `SKILL.md` §4 的决策边界与授权范围。

1. **先有分批计划。** 沿用已谈定的计划，不新建重复方案；还没有就按可独立验证的成果分批，每个任务写明验收命令/观察方法与期望结果，跟用户确认一次。用户已确认过计划或说了“你定”，就不再确认。记录工作区、计划路径、当前提交与已有未提交改动（提交号不能代表整个工作区）。
2. **首次在本宿主上先做隔离小样本，实际验证“监工派执行者”可用**：中间结果进入监工、主会话只收到监工简报；按真实可用名额派工，默认一个在途执行者。不能嵌套时不假装三层可用：明确降为两层短汇报，或采用已经验证可派执行者的独立会话；不自行安装另一套调度系统。
3. **只由主会话启动监工，同一时间一个；不继承完整聊天。** 启动提示给出两个目录下各文件的绝对路径、已定档位/架构/评审与授权结论、工作区、新旧批次/监工标识、计划、HANDOFF 与有效约定路径。新批次首次保存的 revision 来自 `status --batch <上一批ID>`，不是新批次，也不是 missing。模板见下。
4. **收到简报后用下方 `status` 看短摘要，不展开全部执行记录。** 必要的用户决策或独立审计时可定点查证，不能把普通诊断接回来。
5. **替换前停止新派工**；监工完成或确认终止全部执行/验证/文档任务，保存记录。主会话查询宿主状态，确认旧监工及其子任务全部停止（超时、无消息、写了交接都不等于停止）；再运行 `check --ready`。两者都通过才启动下一任。交接写入失败、记录缺失/损坏、项目/批次不符都不得继续。
6. **全部计划完成**且最后一批 ready、宿主确认旧监工及子任务已停止后，主会话派独立文档收尾任务：将有效约定迁入现有规格、将本批证据保留在产物中，再删除 HANDOFF；还有别的未完工作则保留其余区段。这个收尾任务只处理文档，不让主会话读取执行细节。此前任何文档任务都不得删除 HANDOFF 或批次区。
7. **意外结束时先核宿主**，处理仍运行的子任务；原记录保留，接任者核对实际产物与工作区再更新状态。若旧记录仍标 running，先保留旧 supervisor 归属对旧批做事实对账：将已确认结束的执行者及任务改为真实状态并保存，再切换新 supervisor；不能通过换标识绕过 running 检查。这里的 supervisor 是记录归属，不是写入者身份认证，宿主停止仍须独立确认。不因为“有 diff/提交/摘要”就认定任务已实现或已验证，不直接重复执行。**中途故障恢复是异常路径，不是自动轮换**。

启动提示（精确替换占位符，不把整个会话复制进去）：

> 作为本批次实施监工，先按 <vibe-flow目录>/references/role-reading.md 的监工清单读取（仅列明的公共节，不通读父入口），再读 <supervisor目录>/references/supervisor.md、<HANDOFF> 的有效约定与批次区、<计划>，工作区 <绝对路径>，批次 <新ID>，上一批 <旧ID或首次>，你的标识 <宿主ID>，状态脚本 <supervisor目录>/scripts/batch_state.py。切批首次先查询旧批状态取得 revision，再保存新批；只有明确首次建批可 --init --expect missing，恢复时 missing 是损坏，禁止重新初始化。只实施本批次，负责派工、失败诊断/重试、集成、验证与文档。一次一个短执行任务；普通失败在本层解决，同一问题最多三次修复尝试，仍失败就记录 blocker、停止依赖任务，可继续独立任务。新技术取舍按 <vibe-flow目录>/references/collaboration.md 咨询；档位为好·重时必读该文件，按其中密度执行关键步骤结果审；跨用户决策边界才上报。只在子任务全结束后保存交接并退出；上行最多八行：批次状态、成果、必要决策、证据/HANDOFF 路径。不得将完整日志、源码或过程摘要上推；不得自行启动接任监工。档位 <省/好·轻/好·重>，架构/路线与范围 <已定结论>，已完成评审 <证据或不适用>。遵守原计划的修改、提交与发布授权。

## 主会话看状态

```text
python <supervisor目录>/scripts/batch_state.py status --handoff <HANDOFF> --workspace <工作区> --batch <ID> --json
python <supervisor目录>/scripts/batch_state.py check --handoff <HANDOFF> --workspace <工作区> --batch <ID> --ready --json
```

`status` 只给计数、有限证据路径和下一步；`check --ready` 只检查记录，**不能查询、停止或撤销宿主 agent**。保存命令、记录格式与状态规则见 [references/supervisor.md](references/supervisor.md)，主会话不需要读它。
