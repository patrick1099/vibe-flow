# vibe-flow

先读 docs/HANDOFF.md 的已谈定/本批状态，再读 docs/BLUEPRINT.md；相关历史取舍按关键词查 docs/CHANGELOG.md。安装与宿主接入见 SETUP.md。

测试：`python -m unittest discover -s tests -q`（python 代表当前宿主确认的解释器）。协作建议只读入口：`python skills/vibe-flow/scripts/collaboration_config.py --organization single`。

协作工具/成员/角色/组织集中在 skills/vibe-flow/config/collaboration.json，本机覆盖契约见 references/collaboration-config.md。读取脚本不执行 agent。工具原文刷新按 SOURCE.json，经 sync_acpx.py 预演再执行。不要改写 vendored 原文。

版本同时更新 .claude-plugin/plugin.json 与 .codex-plugin/plugin.json。hooks 两平台入口保留共用判定；脚本回归不等于宿主端到端。受透明加密保护的脚本按本机 Esafenet 写入规范处理。
