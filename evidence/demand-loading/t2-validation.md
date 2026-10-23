# t2 独立验收：按需加载最小瘦身 B

> 本文为两项结果审修复前的初验快照；最终针对性复核与字符量见 [t2-review-followup.md](t2-review-followup.md)。

结论：本批文档可验收，没有阻断发现。三个有限前向场景的行为判断符合既定要求；监工实际按职责读取，未替下层加载应用实现分支。直接服务用户的两个场景仍有较多读取，原始量如实保留，不能把本次变更解释成所有请求只读总入口。

范围：工作树 `C:/Users/huawei/.codex/worktrees/vibe-flow-demand-loading`，基线 `5ef3632`。只审规则、原始工件与读取行为，仅在本目录保存证据；未改业务 skill、未写 HANDOFF、未提交或升版。三场景均 `fork_turns=none`，逐个启动，收到结束并通过宿主 completed 确认后才进入下一场景。没有向场景传入预期答案或实现者结论。

## 静态与行为契约核对

- 九个 `skills/*/SKILL.md` 保持九个；以本机绝对 Python 路径运行 skill-creator `quick_validate.py`，九项退出码均为 0。
- 审查 maintained skill Markdown（九入口及 references，排除未改动的 vendor 快照）76 个相对 Markdown 链接出现：74 个真实链接全部可达；2 个是 `scan-field/SKILL.md:78` 围栏示例中的 `[名](链接)`，不作缺失资源。两个带锚链接均已对照实际标题核验。
- 记录并人工核对 71 处数字 § 引用。§1–§9 仍在；跨文件的目标由显式路径、上下文中的 vibe-flow 或 role-reading 开头的目标声明确定。监工启动模板的新技术取舍指向明确 `references/collaboration.md`，不存在裸 §7 依赖。
- 对照基线 diff 与最终 `planning.md/collaboration.md/doc-fork.md/role-reading.md`：架构先讨论、用户授权与决策、已谈定读回、图/原型、低耦合、实际使用检查、文档责任及最终清理权限均保留。公共步骤集中在入口对应节/单一 reference，分支提供本栈落法，角色表只分配读取责任。
- `git diff --check` 退出 0。`git diff --name-only 5ef3632 -- ':(exclude)*.md'` 无已跟踪运行时代码变更。本次未新增措辞匹配型测试，未重复未触及的 207 项运行时回归。

详见 [static-audit.json](static-audit.json)。这些检查不把 quick_validate 当作行为通过的替代。

## 统一字符口径

UTF-8-sig 解码，CRLF/CR 统一为 LF，计 Unicode 字符，不计字节或 token。frontmatter 从起始三横线到结束三横线（含结束符后一个 LF）整体排除；其后的空行属于正文，因此入口正文是 9,221，额外剥掉该空行会得到 9,220，本文不混用两种口径。

| 范围 | 基线含 frontmatter | 当前含 frontmatter | 基线正文 | 当前正文 |
|---|---:|---:|---:|---:|
| vibe-flow 总入口 | 13,650 | 9,768 | 13,090 | 9,221 |
| 九个入口合计 | 49,993 | 46,868 | 45,703 | 42,464 |
| 总入口与六个触及/新增 reference | 23,961 | 26,057 | 23,401 | 25,510 |
| 全部 maintained skill Markdown，24→27 文件 | 94,123 | 96,976 | 89,833 | 92,572 |

这是入口缩小、阶段内容下沉及读取责任显式化；整套维护文本实际增加。未测费用、token 用量、长期上下文收益或相同任务的基线 agent 对照。原始量和文件哈希见 [character-counts.json](character-counts.json)。

## 隔离前向观察

完整用户请求、原始工件及共同只读约束见 [scenario-inputs.json](scenario-inputs.json)。调用和输出来自各场景 session 中实际 tool 事件，含源路径、行号及源文件/输出哈希；未用最终回答中的自报读取清单代替观察。

| 场景 | 行为结果 | 实际读取纪律与限制 |
|---|---|---|
| 已有长期工具按钮明确改名 | 省档、不提澄清/架构审批；只建议改标签并从真实入口检查导出；完成后再读文档流程 | 全文读 flow、apps、native、python-ttk 共4个文件；未读 planning、监工、另一条UI路线、Clean MVVM。属于直接执行小改，未发生父角色替已分派子角色预读。仍读了所选应用链，不能宣称小改只读入口。 |
| 新离线桌面CSV工具、先商量做法 | 给轻结构职责/状态/后台IO及验证方式，等待架构方向认可；未实施、未强套Clean MVVM；未重问已给输入条件 | 读 flow、apps、native 全文；planning先查标题再仅读1–16行架构部分。用户已明确离线本地桌面，apps足以路由原生；native实际含架构/生命周期内容，支持当下讨论，但全文包含更多实现细则，记录为冗余，不把它计作节省。未读语言实现参考或好档方案段。 |
| 已定多任务计划零上下文监工接任 | 沿用好·轻/原生/既定轻架构及原型；不重做已验证t1；从旧批取revision、不得重新init；拟依次实现/独立验证/文档；最终清理留主会话ready后另派 | 实际读role-reading、batch-supervisor、4份工件，查root标题并只向模型返回§4两个公共小节及§6/§8；最后仅列skill路径。未加载apps/native/python-ttk、planning、collaboration或doc-fork全文；按时机把这些路径交下层。Get-Content在进程内可读全文件，模型收到的是指定段落，二者不混称。 |

三个场景均只给下一步/读取清单/问题，不修改真实项目；监工场景中旧任务停止、旧批 ready 是隔离工件给定事实，未进行宿主调度或真实UI验收。场景3的“文件输入命中外部数据”仅是拟传下层的条件理解，本轮未因此实际加载 low-coupling，不据此证明配置规则已运行。

| 场景 | 不同skill文件路径 | 实际命令结果数 | 返回字符（含frontmatter） | 返回字符（剔frontmatter） |
|---|---:|---:|---:|---:|
| 小改 | 4 | 4 | 22,970 | 21,513 |
| 新项目讨论 | 4 | 5 | 20,479 | 19,022 |
| 监工接任 | 3（root仅段落） | 7 | 12,405 | 12,405 |

返回量包含实际返回的标题搜索、路径清单、隔离工件；是观察值，不是仅skill正文之和，也不是完整模型输入。场景输入未计入表内。详见 [scenario-read-metrics.json](scenario-read-metrics.json) 与各 `scenario-*-calls.json`、`scenario-*-raw.jsonl`。

## 未测与交付边界

未执行真实应用实现/界面路径、状态写入、真实多任务批次、跨宿主生命周期、费用或长期上下文对照；实现/验证/文档下层角色的清单做了静态审读，没有再各自增加前向场景。本批文档规则的有限读取与判断观察通过，不等同于这些能力已验证。

原始证据采用显式白名单，只保存场景输入、tool参数、读取输出/哈希/字符量及最终回答；不复制session_meta、账户标识、base_instructions或完整系统/developer指令。外部原始session日志未修改。
