# Hooks 验收记录

2026-11-03，v0.33.0。此记录区分脚本回归与真实宿主事件。

## 本轮补齐

- Codex 的 SessionStart compact 接入共享恢复核心；PostToolUse 只缓存路径事件和 worktree 映射，SessionEnd 清理本会话缓存。
- 文档闸在 Pre/PostToolUse 记录 shell 命令显式提到的候选仓库，Stop 通过实际 Git 变动确认本轮写入；保留原有每轮最多拦一次、receipt 和 deps snapshot 判定。
- 恢复内容仍按原有 HANDOFF 已谈定和项目文档选择规则，未改写历史约定。

## 原生宿主证据

使用 Windows 原生 app-server 0.164.0-alpha.11.1、隔离 CODEX_HOME、临时 Git 项目和仅监听 127.0.0.1 的确定性 Responses 服务。模拟的只有模型输出，工具执行和 hook stdin 都来自真实宿主。

通过 hooks/list 获取 currentHash，再用 config/value/write 写入隔离配置的 hooks.state，回读全部 trusted。thread/start 和 turn/start 显式选择 permissions=:workspace，实际返回 workspaceWrite；沿用 on-request，只批准固定临时测试路径和指定命令，不关闭信任或沙箱。

- 实际 shell 写入另一个独立 Git 仓库的 main.py 后，文件内容改变；Stop 首次 blocked、同一轮随后 Stop completed。只读命令未触发文档阻断。
- exec_command 实际映射为 Bash；tool_input 只有 command。成功 PostToolUse 的 tool_response 为纯 stdout 文本。
- 手动压缩依次发出 PreCompact、PostCompact、SessionStart(source=compact)，后者没有 turn_id。实际恢复脚本输出的约定标记进入下一轮模型输入；SessionEnd 清理回调 completed。
- 原生 exec_command 的独立 workdir 不进入 hook stdin，顶层 cwd 仍是 thread.cwd。命令显式路径可以定位候选仓库，只有相对路径且依赖被省略 workdir 的跨仓写入仍无法可靠定位。
- apply_patch 捕获到真实 PreToolUse；对精确临时目标正常批准后，工具等待 90 秒仍未完成，没有文件落地或成功 Post。此项仅有既有成功回调样本与逻辑回归，不能称当前宿主成功链已验证。

采集器最初额外启动第二个 Python，导致宿主固定 3 秒的 SessionEnd 超时。改为同一解释器运行真实脚本后完成；公开插件保留直接启动脚本，不增加包装进程。

## 范围与限制

候选提取不等同于解释任意脚本。动态计算的目标、不可见的 MCP 写入和丢失 workdir 的相对路径不能保证发现；失败命令若已部分写入，Pre 候选结合实际 Git 变动仍可发现。安装前未记录的跨仓历史不在缓存中，恢复仍以当前 cwd 作为后备。

真实宿主使用 py -3 成功启动回调；普通路径和带重复分隔符路径均未复现历史 Claude Desktop Python getpath 启动故障。本轮不改公开启动命令，也不将本机解释器路径写进插件；历史桌面故障保留待复现。

## 回归

`python -B -m unittest discover -s tests` 全量 288 项通过（959 秒）；纯 stdout 样例更新后，压缩适配 8 项另行通过。定向原生适配测试 61 项通过，覆盖跨仓 dirty、只读、旧 dirty、失败后部分写入、隔离清理、worktree 移动及无 turn_id 压缩。

发布时需要同时更新两个 plugin manifest、hooks/codex.json 与 hooks/ 下共享及适配脚本。安装后按宿主当前 hash 审查并信任；旧缓存不视为新脚本已加载的证据。
