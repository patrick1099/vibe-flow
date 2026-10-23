# 交接 · 2026-10-23

## 已谈定

- 2026-10-23 · 用户 · 同意最小瘦身 B：保持九个 skill，不新增独立架构/监工 skill；精简总入口，重复步骤下沉按需 references；主会话只读路由，角色按明确读取清单加载；修复监工裸 §7 引用，保留架构讨论、用户决策和其他已确认行为。

- 2026-10-23 · 用户 · 采纳 Astra 与 Claude 评审后的首版：主会话只管计划、必要决策与短简报；监工负责整批实施、日常排错、验证和文档收尾；无在途执行者才交接，主会话启动不继承完整聊天的新监工。先验证主会话退出执行细节，不做上下文阈值自动重启、在途迁移或大型调度平台。

- 2026-10-23 · 用户 · 已要求将本候选合并到主分支，采用本轮项目架构讨论与可选 Clean MVVM 规则；此前暂不合并的限制解除，按插件交付约定升版、推送与同步，其他候选和 serial-split 不改。

- 2026-10-23 · 用户 · 新项目开始前像方案一样讨论架构，具体结构看项目情况；Clean MVVM 是重点候选，不统一强制。已有项目普通修改沿用已定方向。本条当时的“只改候选 worktree、是否采用待定”已由同日后续合并授权解除。

- 2026-10-19 · 用户（历史约定，采用限制已由 2026-10-23 后续授权解除）· 先在独立 worktree 更新 Clean Architecture + MVVM 规范候选，当时不合并、推送、发布或刷新安装；不修改 serial-split 和原有 Zig 候选的范围限制仍有效。

- 2026-10-15 · 用户 · 应用界面效果图先行：原生 GUI 只靠文字需求让 AI 写，观感很差；新应用、新页面、布局大改先出 HTML 效果图，用户在浏览器里改到满意，再让 AI 照图实现。
- 2026-10-15 · 用户 · DESIGN.md 从 Web 分支上移，原生与 Web 共用，作为颜色、字体、间距的唯一来源；取消“单页不建”。
- 2026-10-15 · 用户 · 纯 Rust 原生 GUI 固定用 Slint；egui、iced 等其他 Rust UI 不再考虑。
- 2026-10-15 · 采纳 codex 建议 · designmd 0.4.0 导出不完整（css-vars 无字体；css-vars 与 dtcg 都不导 components；dtcg 丢无单位 lineHeight），不能当无损转换器，导不出的值不许静默丢；`omitted` 只表示设计有意不定义某节，不用来声明框架能力，能力清单写进语言参考；状态按实际功能选，用一个可切换状态的 HTML；Tk 字号 px 要写成负数；截图对照由 AI 先做、比观感不比像素、第一版布局出来就对照。
- 2026-10-15 · 用户（未反对 AI 提议）· 分两批：第一批只改 skill 文本；第二批写 DESIGN.md → ttk / Slint 主题生成器（生成器放插件、产物放项目、不支持的字段报错）。
- 2026-10-15 · 用户 · 第二批现在就开始做，不再等真实项目（推翻上一条里的“等真实项目时再做”）。
- 2026-10-15 · 用户 · serial-split 保持现状：运行中参数照旧置灰，不加 HEX 行的 ASCII 列。
- 2026-10-15 · 用户 · 原生两条路分工：ttk 管开发敏捷，Slint 管内存和性能，默认仍 ttk；效果图大量落在 ttk 能力清单第二列时，一两句话说明后果、问用户换不换 Slint，不替他换。

## 0.25.0 交付说明 · 2026-10-23

批次监工工作流、HANDOFF 状态工具及 GSD / Gas Town 原文同步入口已实现，使用说明见 README「已确定计划的批次监工」及
`skills/vibe-flow/references/batch-supervisor.md`。状态工具是机械记录闸，不能代替宿主生命周期控制或语义验收。

当前 Codex 工具已完成两任监工实验：首任派实现、独立验证、文档三个任务，初始失败由监工层处理；接任者不继承前任历史，
从磁盘恢复并独立验证五项通过，未重复实施、未改代码。两任监工及全部执行者均已结束，最终 ready 已复查。
结果评审已补齐旧批 ID 取 revision、等待文档任务结束、保护机器区与独立最终清理、仅首次 `--init`，以及机器区独立标题。

合入 0.24.0 后的完整回归已结束：207 项全通过（210.375 秒）；九个 skill 的 `quick_validate` 全通过，11 个本地链接无缺失。
隔离实验最终文档清理完成：有效约定保留在 BLUEPRINT，HANDOFF 已删除，`evidence/cleanup.json` 记录删除前哈希与清理结果。
Claude / opencode 生命周期、长期上下文与 token 收益、两层短汇报对照尚未实测；本区不复制具体任务进度。

## 0.24.0 采用记录 · 2026-10-23

- 工作树：`C:/Users/huawei/.codex/worktrees/vibe-flow-clean-mvvm`，分支 `feat/clean-mvvm-candidate`，从 `main` 的 `f0aac98` 独立建立；不是 Zig + Dear ImGui 候选，原候选保留。
- 当前规则：新项目开始前讨论架构，按规模给推荐、理由、职责/状态/任务边界和验证方式，方向谈定后实现；已授权 AI 决定或方向已确认，不重复审批。Clean MVVM 是重点候选，选定后才套相应契约；小工具允许更简单结构，旧项目普通修改不自动迁移。
- 已完成：同步总入口、架构图说明、应用共用入口、Clean MVVM reference、原生/Web 分支及 ttk/Slint 映射。按复核明确了 ViewModel 的 UI 线程所有权、幂等异步退出、向内但不必逐层转发的依赖、注册表的 IO 边界、Rust 可测试内层与 Web 开发测试工具；验证按改动规模安排，区分自动覆盖、人工核对和真实界面/设备验证。局部迁移须明确范围，不默认允许 View 绕过 ViewModel 调新用例。
- 外部复核：2026-10-22 用户明确授权后，已通过 ai-room 完成 Claude 只读复核，结论是方向可用但不宜原样采用；本批据其执行细节问题及 2026-10-23 用户意见调整。本批没有再次外审。此前自动审批拒绝是授权前的历史情况，不是当前阻塞。
- 本次交付验证（2026-10-23）：185 项既有回归通过（301.415 秒）；四个 skill 的 `quick_validate`、两份 `0.24.0` 版本 JSON、20 个本地 Markdown 链接及 `git diff --check` 通过。文档 fork 前后非 Markdown 哈希一致（`eb6ff121a40a3bc921196b391725d0b3ae71e226952321c65248967803623282`）；同步前 `hub health` 全部正常。
- 前一轮候选文档验证（2026-10-23，非本次升版后的最终结果）：四个 skill 的 `quick_validate` 通过；当时全部 11 个改动文件仅 Markdown、21 个本地 Markdown 链接有效，`git diff --check` 通过；文档 fork 前后非 Markdown 哈希一致。
- 历史验证（2026-10-19，非本轮重跑）：`unittest discover -s tests -q` 共 185 项通过（128.933 秒），当时四个 skill 验证、16 个本地链接与 diff 检查通过。既有插件回归不等于 Clean MVVM 已在真实应用或跨语言架构闸验证，也不代表界面或真机验收。
- 采用与范围：用户已决定采用并合并到主分支，双平台版本为 `0.24.0`。本次只更新工作流规则，不修改 `serial-split` 或 Zig 候选；提交、合并与推送结果以 Git 记录为准，同步结果由交付回复报告。

## 留给下次（不是本次任务）

效果图先行两批都已完成（0.22.0–0.23.0，见 README「沿革」）。只剩一条待核实：Web 路线的 `web/theme.css` 若由 python 进程写出，本机 Esafenet 也会把它加密——浏览器经 FastAPI 取到的是明文、不受影响，但用 file:// 直接打开页面会丢样式。下次真做 Web 项目时实测一次，再决定要不要像原生效果图那样把 token 写进 HTML。

## 架构沟通的当前口径

0.13.2–0.13.3 曾试行“架构层只看，AI 说明后直接做”。2026-10-23 用户明确提出“在每次开始项目之前，可以进行架构讨论这种，与方案讨论一样”，并已要求合并到主分支；0.24.0 据此替代旧试行。

新项目先讨论适合它的架构，用户参与决定方向，也可以授权 AI 决定；不把 Clean MVVM 统一套到所有项目。方向谈定后，具体文件、API 和工具由 AI 处理，细化图用于说明，不重复审批。现有项目普通修改沿用已定架构，仅在新目标、迁移要求或边界变化需要时重谈相关部分。

规则位置：`skills/vibe-flow/SKILL.md` §4、`skills/clarify-needs/references/run-model.md` 与 `skills/vibe-apps/SKILL.md`。采用方向已确认，不再以旧“架构只看”试行要求覆盖本次用户意见。

# 本批计划：按需加载最小瘦身

基线：5ef3632，独立工作树创建时干净。本批执行负责人是 /root/demand_loading_supervisor，主会话不接回普通实施、排错、验证与文档任务。

- t1：按已评审 B 收敛总入口。保留 §1–§9 编号及行为闸（意图、档位、用户授权/决策、已谈定、架构先讨论、低耦合底线、文档表、实际使用检查）；优先去重与下沉外援/阶段步骤，保留按时机路径。分支对“先读父入口”的要求区分直接服务用户与已分派角色，角色获得明确最小公共契约和适用结论，不能因减读丢弃约束。监工调用外援规则须有明确文件路径，禁止裸 §7 依赖。不要一章拆一文件，不追固定行数，不改已采用 Clean MVVM、图/原型、文档/交接或小改直做等预期行为。
- t2：独立验证。九个入口数量/加载有效，所有 §N 引用与本地链接可达；比较真实正文体量（字符/文件读取量，不夸大为计费或长期上下文收益）。至少覆盖小改、新项目架构讨论、已定计划监工接任三个隔离场景，检查应问/不问、角色读取路径、阶段遗漏。合理控制试验规模，不构建新的统计平台。只改文档时不为形式重复全部未触及运行时测试。必要时按 skill-creator 做独立前向测试。
- t3：收尾。由文档任务更新现有 README/沿革，保留 HANDOFF 已谈定与机器区和其他既有事项；版本升0.25.1，独立只读结果评审（方案已由两人审过，不重审）。全部子任务结束后保存 ready，最多8行汇报成果、验证、体量、证据和 blockers。

权限：仅本 worktree，工具创建的隔离测试目录；不改公司固件、不改其他候选、不动安装缓存/全局配置。监工可将本分支提交供主会话合并；禁止自行主线合并、推送或 hub sync，最终交付由主会话执行。Python使用本机绝对路径。普通内部选择监工决定，跨用户决策边界再上报。

# 批次状态

<!-- vibe-flow:batch:start -->
```json
{
  "schema": 1,
  "workspace": "C:\\Users\\huawei\\.codex\\worktrees\\vibe-flow-demand-loading",
  "batch": "demand-loading-b1",
  "supervisor": "/root/demand_loading_supervisor",
  "baseline": "5ef3632; initial worktree clean",
  "outcome": "complete",
  "docs": "done",
  "tasks": [
    {
      "id": "t1",
      "state": "verified",
      "acceptance": "preserve behavior and sections; retain 9 skills; real entry reduction with conditional role reading",
      "evidence": [
        "evidence/demand-loading/t1-implementation.md",
        "evidence/demand-loading/t2-validation.md",
        "evidence/demand-loading/t1-review-followup.md",
        "evidence/demand-loading/t2-review-followup.md"
      ]
    },
    {
      "id": "t2",
      "state": "verified",
      "acceptance": "independent three-scenario review plus validators and resolvable references; report actual checks",
      "evidence": [
        "evidence/demand-loading/t2-validation.md",
        "evidence/demand-loading/t2-review-followup.md",
        "evidence/demand-loading/final-character-counts.json"
      ]
    },
    {
      "id": "t3",
      "state": "verified",
      "acceptance": "documentation and 0.25.1 manifests; independent result review; all workers ended and ready",
      "evidence": [
        "evidence/demand-loading/t3-documentation.md",
        "evidence/demand-loading/t3-result-review-receipt.json",
        "evidence/demand-loading/t2-review-followup.md",
        "evidence/demand-loading/final-ready.md"
      ]
    }
  ],
  "workers": [
    {
      "id": "/root/demand_loading_supervisor/implement_t1",
      "state": "done"
    },
    {
      "id": "/root/demand_loading_supervisor/validate_t2",
      "state": "done"
    },
    {
      "id": "/root/demand_loading_supervisor/docs_t3",
      "state": "done"
    },
    {
      "id": "ai-room:claude-result-review",
      "state": "done"
    }
  ],
  "next": [
    "主会话确认监工及子任务停止后，独立清理本批计划/机器区并保留其他历史，再按授权交付"
  ]
}
```
<!-- vibe-flow:batch:end -->
