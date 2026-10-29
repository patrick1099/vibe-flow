# 批次监工：执行、保存与状态工具

主会话的启动与交接见 [../SKILL.md](../SKILL.md)；本文件给监工及接任者读。`<vibe-flow目录>` 指同插件的 `skills/vibe-flow`。

## 监工：执行与保存

- 先核项目、工作区、批次、基线和已有改动，读取有效约定。监工不改「已谈定」；需用户决定时将具体影响上报主会话，由其更新约定。
- 派工前按 [role-reading.md](../../vibe-flow/references/role-reading.md) 传结论与具体角色读取路径，不让执行者重判档或全读父入口；保存任务与运行者状态；得到宿主 ID 后立即补记。实现完成、验证完成分别保存；超时先查真实状态与产物，不重发同一任务。
- 执行者只写自己任务的产物/证据；监工单独写机器批次区。批次区是该批进度唯一出处，其他 HANDOFF 文字只保留必要恢复说明，不在看板或记忆再复制任务状态。
- 实现和验收分开：独立验证任务按计划检查用户可见行为，保存命令、退出码/观察结果与必要产物。监工审查证据与偏差，文件存在不代表正确；状态工具不替代语义验收。
- 失败先分类：修复任务导致的问题；无关既有失败记录，不擅自扩范围；限流等待不当死锁。短核对可以自己做，长排错委派。涉及数据/设备的操作按已授权边界，危险动作立即停。
- 收工按 [doc-fork.md](../../vibe-flow/references/doc-fork.md) 派文档任务，继承监工上下文；文档任务结束后监工保存最终批次状态。不得因文档闸要求主会话读回 diff。
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
- 来源、commit、哈希与许可证在 `../vendor/upstream.json`、`../vendor/upstream.lock.json` 及各目录 LICENSE。用已有同步器更新：`python <插件>/skills/vibe-apps/scripts/sync_upstream.py --vendor-dir <subagent-foreman目录>/vendor`；加 `--check` 仅比对。
