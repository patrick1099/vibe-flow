# acpx 接入与原生验证

配置首先指向本页；调用前先读本页已验证的模型/权限恢复规则，再按需读链接的上游原文。上游原文可能包含当前适配器不可用的复合模型 ID 与 set-mode 示例，日常恢复采用本页实测命令，不照抄未验证变体。

此页记录当前工具接入，日常协作规则见 [collaboration-config.md](collaboration-config.md)。版本按实测锁定 0.22.0；切换工具只改配置与该工具的说明，不改主流程。

## 安装与工具说明

```text
npm install --global acpx@0.22.0
npm install --global @agentclientprotocol/codex-acp@2.6.0 @agentclientprotocol/claude-agent-acp@0.107.0
acpx --version
acpx --help
acpx codex exec --help
acpx config show
```

先确认 Node/npm、当前 shell 与宿主运行账号、适配器和后端认证。不要把临时 npm cache 中的入口写进长期配置。Windows 推荐把适配器装到持久 npm 全局目录，使用 `npm root --global` 和当前 `node` 命令的实际路径定位，核对包内入口；本机路径写进 `~/.acpx/config.json` 的原生 `agents` 配置。

当前已核适配器版本：`@agentclientprotocol/codex-acp@2.6.0`、`@agentclientprotocol/claude-agent-acp@0.107.0`。按本机能力验证后安装；OpenCode 使用本机已验证的 `opencode acp`，不要将模型 ID 假定为所有供应商通用。

原始文档在 [vendor/acpx/SKILL.md](../vendor/acpx/SKILL.md)，MIT 许可见 [LICENSE](../vendor/acpx/LICENSE)，包版本、原始 URL 和文件来源见 [SOURCE.json](../vendor/acpx/SOURCE.json)。这份原文保留上游链接，源包外相对链接需去上游仓库查看。刷新入口：

```text
python skills/vibe-flow/scripts/sync_acpx.py --dry-run
python skills/vibe-flow/scripts/sync_acpx.py
```

它按 SOURCE.json 的固定版本抓取 npm 原包，验证包名/版本，只同步登记的原文与许可；预演与执行共用同一写入路径。升级需同时修改工具配置版本、SOURCE 与验收证据，不能自动追随 latest。

## Windows 原生 argv

acpx 0.22.0 支持原生 `argv` 数组，Windows 不拼含空格的 shell 命令。以下 JSON 展示形状，尖括号内容须替换为本机解析出的真实路径，不能直接复制运行；本例不是新的模板语言：

```json
{
  "agents": {
    "codex": {"argv": ["<node绝对路径>", "<全局npm根>/@agentclientprotocol/codex-acp/dist/index.js"]},
    "claude": {"argv": ["<node绝对路径>", "<全局npm根>/@agentclientprotocol/claude-agent-acp/dist/index.js"]},
    "opencode": {"argv": ["<opencode可执行文件绝对路径>", "acp"]}
  }
}
```

实际包入口以安装包 `package.json` 的 `bin` 字段为准；运行 `acpx config show` 核对解析结果。共享建议文件只保存工具/模型/说明来源，本机 argv 仍由 acpx 自己读取，不复制进另一套驱动。配置里不要存个人 token，也不要把认证配置完整打印到记录。

## 一次性咨询与修改任务

下列是从 0.22.0 帮助核对的原生命令示例，agent、模型和权限在任务约定中按用户确认值替换。`--config-option` 是 `exec` 参数，不能移到全局或持久 `prompt` 上。示例文件为任务输入，先核对读出的是明文。

```text
acpx --cwd <工作树绝对路径> --format json --json-strict --deny-all --timeout 300 codex exec --config-option model=gpt-6.1-sol --config-option reasoning_effort=medium --config-option mode=read-only --file review.md
```

修改任务只在隔离临时目录验证，使用用户确认的 agent/model/mode 与真实写权限，要求创建一个指定文件；负责人检查内容、diff 和退出码。不要把 `--deny-all` 当操作系统沙箱：它控制 ACP 权限请求，后端可能自行执行工具；也要检查后端 mode 和实际拒写结果。Claude 原生审批也可能先于 ACP 权限，必须单独实测。

## 命名会话与恢复

先建明确命名会话，再使用同一 `--cwd`、agent、适配器 argv 和名字。下面三项设置分别独立，不把 effort 塞进模型 ID：

```text
acpx --cwd <工作树绝对路径> --format json codex sessions ensure --name task-review
acpx --cwd <工作树绝对路径> --format json codex set model gpt-6.1-sol -s task-review
acpx --cwd <工作树绝对路径> --format json codex set reasoning_effort medium -s task-review
acpx --cwd <工作树绝对路径> --format json codex set mode read-only -s task-review
acpx --cwd <工作树绝对路径> --format json --json-strict --deny-all --timeout 300 codex -s task-review --file followup.md
```

每次重连/恢复均按原任务已确认设置重新应用并检查 ACP `configOptions`/模型目录接受值。0.22.0 实测中单独 `set-mode read-only` 的 mode 在下一次 load 后回到默认；`set mode read-only` 走配置选项回放才保持。不能据「set 返回成功」宣称 prompt 时仍生效。模型 `gpt-6.1-sol[medium]` 在当前适配器不接受，用 plain model 和独立 effort。

```text
acpx --cwd <工作树绝对路径> --format json codex status -s task-review
acpx --cwd <工作树绝对路径> --format json codex sessions show task-review
acpx --cwd <工作树绝对路径> --format json codex sessions history task-review --limit 10
acpx --cwd <工作树绝对路径> --format json codex sessions read task-review
acpx --cwd <工作树绝对路径> --format json codex cancel -s task-review
```

同一会话的后续任务会排队；需仅取排队确认时用 `codex --no-wait -s task-review --file next.md`，之后从原生 history/read/watch 获取结果。排队确认不是完成回执。外层被杀先查状态/历史，不重发；`sessions show` 核对原生 ID，后端无法恢复而工具新建会话时停止并报告。不要 `prune` 旧历史。

## 验收边界

配置脚本离线验证：

```text
python -m unittest discover -s tests -p test_collaboration_config.py -v
```

首次安装/换机逐项验：配置替换成员与模型后建议随之改变；坏配置、无效角色引用、缺说明退出非零；真实咨询；临时文件修改与负责人复核；后端拒写及恢复后权限；命名多轮/关闭后续接/外层被杀；取消/队列/原生 NDJSON 与退出码。模型、effort、mode 在创建和恢复后均保留原始 ACP 接受值证据。

2026-11-16 正式安装验证（主会话原始汇总：`%TEMP%/acpx-deploy-20261116/summary.json`）：一次性咨询 rc0，ACP 接受 model=gpt-6.1-sol、reasoning_effort=medium、mode=read-only；持久记忆恢复 rc0；恢复后拒写 rc0，文件不存在且三项设置仍正确。OpenCode 用实际支持的 big-pickle/build 创建文件并由负责人逐字核对，复验 rc0；其没有 effort 能力，不能给它伪造 effort 值。

外层前端被杀后同会话仍可查询；排队确认 rc0、取消 rc0、历史中排队任务已完成，续接返回正确记忆；另一工作目录同名会话查找按预期失败。原始失败也保留：复合模型 ID rc1；set-mode 不在 load 后回放；最初文件修改和 secure recall 在 120 秒预算后超时 rc3，串行拉长到 300 秒复验后成功。Claude OAuth expired rc1，认证未通过；长期生产负载未验证。不能把这些限制写成全部后端完成迁移。

## 旧入口退役

旧 CLI 源仓保留历史文档及退役说明；共享 skill 供应入口移除，精确卸载/双 Scripts 入口与 Claude SessionStart 注册清理由部署负责。旧 `.ai-room`、ledger、inflight、房间数据库和原生会话完整保留，不会自动导入 ACP。旧会话的追查方式在 ai-room 源仓 `docs/install-and-rollback.md`，新任务使用本页原生命名会话。
