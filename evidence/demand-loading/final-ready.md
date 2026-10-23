# 0.25.1 最终批次复核

批次 demand-loading-b1；分支 feat/demand-loading；基线 5ef3632。

- t1、t2、t3 及三项有限前向场景均已收到完成回执；2026-10-23 宿主列表无运行中的下层任务，监工本身在最终回复后退出。外援原调用 exec session 63490 已 exit 0，Claude opus/max 保持默认，changed_files 为空。
- 独立结果审判定无阻断、可交付；其微脚本汇报与好·重触发建议已补齐，t2-review-followup.md 记录定点独立复核。未重新方案审，未重复三场景或207项运行时回归。
- 初验九项 quick_validate、74真实本地链接与71处数字节引用通过；范围写法的逐节展开解释见结果审。修复后根入口校验、38相关链接、diffcheck通过；最终README新增7链接可达，lint增量exit0，完整lint存量错误保持并如实披露。
- 最终正文：入口13090→9281（减少29.1%）；九入口45703→42524；全部维护正文89833→92696（增加）。仅Unicode字符，不宣称token、费用、长期上下文或真实应用/宿主调度收益。
- 两份插件manifest均0.25.1；现有tracked非Markdown改动仅这两个版本字段，没有运行时代码改动。证据目录只含Markdown、JSON及JSONL。
- 文档续接前后非Markdown代码指纹相同：`0917e4ad22225927307c213831f24f3bcfc1c349c70df595048b222b264007f1`。
- HANDOFF历史相对基线只插入主会话已授权的最小B约定及空行，无删除/替换；其他历史与有效约定保留。本批计划和机器区仍在，未执行最终清理。
- 未合并主线、未push、未hub sync；提交由本分支保存，最终清理由主会话确认监工及子任务停止后另派。

## 最终ready检查

下方结果由 batch_state.py 实际执行后追加。脚本不能证明宿主停止；宿主状态已另核。

```json
{"ok": true, "data": {"batch": "demand-loading-b1", "supervisor": "/root/demand_loading_supervisor", "outcome": "complete", "docs": "done", "tasks": {"verified": 3}, "running_workers": 0, "next": ["主会话确认监工及子任务停止后，独立清理本批计划/机器区并保留其他历史，再按授权交付"], "evidence": ["evidence/demand-loading/t1-implementation.md", "evidence/demand-loading/t2-validation.md", "evidence/demand-loading/t1-review-followup.md"], "revision": "7ae87499fb359db828e2dd4b9d6a921f241d25510393ada88705aec361defb36", "host_lifecycle_checked": false}, "error": null, "meta": {}}
```

检查退出码：0。

## 暂存后的最终格式检查

首次暂存发现两份新增reference的EOF多余空行（未跟踪时普通diffcheck未覆盖），仅删除两字符后同步最终计量：全部维护正文92,696。此后实际 `git diff --cached --check` exit 0；root正文仍9,281。没有语义变更，原三场景和独立复核的时间快照保留。
