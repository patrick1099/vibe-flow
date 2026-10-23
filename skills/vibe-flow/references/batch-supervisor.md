# 按批次实施：主会话、监工与执行者

## 主会话：启动与交接

适用于已谈定的多任务计划；不改变 [../SKILL.md](../SKILL.md) §4 的授权范围，不默认把简单修改变成三层。

1. 将计划按可独立验证的成果分批，每个任务写明验收命令/观察方法与期望结果。沿用现有计划，不新建重复方案。记录工作区、计划路径、当前提交与已有未提交改动（提交号不能代表整个工作区）。
2. 首次在隔离小样本中实际验证宿主支持“监工派执行者”，确认中间结果进入监工、主会话只收到监工简报；按真实可用名额派工，默认一个在途执行者。不能嵌套时不假装三层可用：明确降为两层短汇报，或采用已经验证可派执行者的独立会话；不自行安装另一套调度系统。
3. 只由主会话启动监工，同一时间一个；不继承完整聊天。启动提示给本文件、[role-reading.md](role-reading.md) 的绝对路径、已定档位/架构/评审与授权结论、工作区、新旧批次/监工标识、计划、HANDOFF 与有效约定路径。新批次首次保存的 revision 来自 `status --batch <上一批ID>`，不是新批次，也不是 missing。零上下文提示模板如下。
4. 收到简报后用下方 `status` 看短摘要，不展开全部执行记录。主会话仍可在必要的用户决策或独立审计时定点查证，不能把普通诊断接回来。
5. 替换前停止新派工；监工完成或确认终止全部执行/验证/文档任务，保存记录。主会话查询宿主状态，确认旧监工及其子任务全部停止（超时、无消息、写了交接都不等于停止）；再运行 `check --ready`。两者都通过才启动下一任。交接写入失败、记录缺失/损坏、项目/批次不符都不得继续。
6. 全部计划完成且最后一批 ready、宿主确认旧监工及子任务已停止后，主会话派独立文档收尾任务：将有效约定迁入现有规格、将本批证据保留在产物中，再删除 HANDOFF；还有别的未完工作则保留其余区段。这个收尾任务只处理文档，不让主会话读取执行细节。此前任何文档任务都不得删除 HANDOFF 或批次区。
7. 意外结束时先核宿主，处理仍运行的子任务；原记录保留，接任者核对实际产物与工作区再更新状态。若旧记录仍标 running，先保留旧 supervisor 归属对旧批做事实对账：将已确认结束的执行者及任务改为真实状态并保存，再切换新 supervisor；不能通过换标识绕过 running 检查。这里的 supervisor 是记录归属，不是写入者身份认证，宿主停止仍须独立确认。不因为“有 diff/提交/摘要”就认定任务已实现或已验证，不直接重复执行。**中途故障恢复是异常路径，不是自动轮换**。

启动提示（精确替换占位符，不把整个会话复制进去）：

> 作为本批次实施监工，先按 <本skill绝对路径>/references/role-reading.md 的监工清单读取（仅列明的公共节，不通读父入口），再读 <本文件绝对路径>、<HANDOFF> 的有效约定与批次区、<计划>，工作区 <绝对路径>，批次 <新ID>，上一批 <旧ID或首次>，你的标识 <宿主ID>。切批首次先查询旧批状态取得 revision，再保存新批；只有明确首次建批可 --init --expect missing，恢复时 missing 是损坏，禁止重新初始化。只实施本批次，负责派工、失败诊断/重试、集成、验证与文档。一次一个短执行任务；普通失败在本层解决，同一问题最多三次修复尝试，仍失败就记录 blocker、停止依赖任务，可继续独立任务。新技术取舍按 <本skill绝对路径>/references/collaboration.md 咨询；档位为好·重时必读该文件，按其中密度执行关键步骤结果审；跨用户决策边界才上报。只在子任务全结束后保存交接并退出；上行最多八行：批次状态、成果、必要决策、证据/HANDOFF 路径。不得将完整日志、源码或过程摘要上推；不得自行启动接任监工。档位 <省/好·轻/好·重>，架构/路线与范围 <已定结论>，已完成评审 <证据或不适用>。遵守原计划的修改、提交与发布授权。

## 监工：执行与保存

- 先核项目、工作区、批次、基线和已有改动，读取有效约定。监工不改「已谈定」；需用户决定时将具体影响上报主会话，由其更新约定。
- 派工前按 [role-reading.md](role-reading.md) 传结论与具体角色读取路径，不让执行者重判档或全读父入口；保存任务与运行者状态；得到宿主 ID 后立即补记。实现完成、验证完成分别保存；超时先查真实状态与产物，不重发同一任务。
- 执行者只写自己任务的产物/证据；监工单独写机器批次区。批次区是该批进度唯一出处，其他 HANDOFF 文字只保留必要恢复说明，不在看板或记忆再复制任务状态。
- 实现和验收分开：独立验证任务按计划检查用户可见行为，保存命令、退出码/观察结果与必要产物。监工审查证据与偏差，文件存在不代表正确；状态工具不替代语义验收。
- 失败先分类：修复任务导致的问题；无关既有失败记录，不擅自扩范围；限流等待不当死锁。短核对可以自己做，长排错委派。涉及数据/设备的操作按已授权边界，危险动作立即停。
- 收工按 `doc-fork.md` 派文档任务，继承监工上下文；文档任务结束后监工保存最终批次状态。不得因文档闸要求主会话读回 diff。
- `complete` 仅在本批全部任务 `verified` 且文档收尾完成时使用；否则保存 `blocked` 与下一步。上下文不足也先收尾最小安全任务，禁止带在途执行者交接。

## 状态工具：复用 HANDOFF，不另建状态库

`<脚本>` 指本 skill 的 `scripts/batch_state.py`；Python 使用宿主可用解释器，本机 Codex 按全局约定用绝对路径。

```text
python <脚本> status --handoff <HANDOFF> --workspace <工作区> --batch <ID> --json
python <脚本> save --handoff <HANDOFF> --workspace <工作区> --batch <ID> --input-file <记录.json> --expect <status返回的revision或missing> --json
# 首次建批在 save 上另加 --init --expect missing；后续保存用 status 的 revision
# b1 -> b2：先 status --batch b1，首次 save 新记录时 --batch b2 --expect <b1的revision>
python <脚本> check --handoff <HANDOFF> --workspace <工作区> --batch <ID> --ready --json
```

save 用内容版本检查及原子替换保存到 HANDOFF 机器区，保留区外文字；`--dry-run` 同路径校验但不写。只有已确认首次建批时使用 `--init --expect missing`，保留其他文字；已存在过批次却读到 missing，属于丢失/损坏，禁止自行初始化。脚本无法单凭文件缺失证明它从未存在，首次初始化授权是工作流边界，不宣称删除防护。损坏区不允许静默重建。任务/运行者标识唯一，一次最多一个 running；verified 需存在工作区内的证据文件；complete 需全 verified、文档完成且没有 running。切换批次前旧批次须 ready，旧证据须随产物/版本历史保留，HANDOFF 只存当前批。

最小记录形状（`baseline` 记录提交和已有改动路径；路径为工作区相对路径）：

```json
{
  "schema": 1,
  "workspace": "<工作区绝对路径>",
  "batch": "b1",
  "supervisor": "<宿主ID>",
  "baseline": "<提交号；已有改动路径或无>",
  "outcome": "active",
  "docs": "pending",
  "tasks": [{"id": "t1", "state": "pending", "acceptance": "命令/观察方式及期望结果", "evidence": []}],
  "workers": [],
  "next": ["开始 t1"]
}
```

任务 state：pending/running/implemented/verified/blocked；运行者：`{"id":"宿主ID","state":"running|done|stopped"}`；outcome：active/complete/blocked；docs：pending/done/not-needed（not-needed 是按 doc-fork 如实判定，不豁免缺文档）。`status` 只给计数、有限证据路径和下一步，不输出完整任务/验收/日志。`check --ready` 检查记录中的 running、收尾和证据；**不能查询、停止或撤销宿主 agent，也不能阻止直接绕过脚本的工具调用**。宿主状态核对及角色边界是工作流约定，不能宣称为代码硬闸。状态损坏或写失败时保留现场，修复/恢复后重查，不凭记忆重建为 complete。

## 验证边界与参考

首版提供工作流与机械记录闸，不承诺宿主自动重启、跨父接管或上下文阈值。每个平台分别以真实嵌套/消息路由、普通失败自治、干净上下文续接来验证；功能正确、故障恢复和主会话上下文收益分别报告。另以相同规模任务对照“两层＋短汇报”，不预设 30% 等未经实测的收益门槛。

上游原文按需读，正文不复制上游流程：
- [GSD manager](../vendor/gsd/manager.md)、[context budget](../vendor/gsd/context-budget.md)。
- [Gas Town Witness](../vendor/gastown/witness.md)、[handoff 实现](../vendor/gastown/handoff.go)。
- 来源、commit、哈希与许可证在 `../vendor/upstream.json`、`../vendor/upstream.lock.json` 及各目录 LICENSE。用已有同步器更新：`python <插件>/skills/vibe-apps/scripts/sync_upstream.py --vendor-dir <本skill>/vendor`；加 `--check` 仅比对。
