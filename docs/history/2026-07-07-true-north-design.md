# true-north 插件设计 spec

> 日期:2026-07-07
> 状态:设计定稿(brainstorming 产出),待写实施计划
> 一句话:一个**与技术栈无关、意图驱动**的个人 Claude Code 插件,把「记录真实需求 / 对内剪枝 / 对外扫同款」三件事收成一套手动、只读为主的设计反思工具。

## 1. 由来与真实需求

起点是 Ponytail 的「过度工程审查」思路,但明确**舍弃它的自动 hook**——理由:*提前知道哪些有人做过、哪些被判过度,会污染 AI 的思考*。所以本插件**全手动触发**。

真正想要的是两个工作流能力,加上一个已有的记录能力,构成一条闭环:

1. **记**:项目在演进,得有一份「当前真实需求 / 功能全貌」的活文档,让 AI 照意图干活、不逆向猜代码。→ 已有 skill,即将改名 `living-blueprint`。
2. **对内剪**:某产品用 superpowers 优化好几轮后,设计会膨胀。需要手动触发一个东西,**读文档理解我真正的需求,做剪枝、纠正方向**——只给方向,不替我改文件。→ 新 skill `cut-scope`。
3. **对外扫**:一个项目做完后,去市面上搜有没有同款 / 更优方案,产出对比与升级方向文档。→ 新 skill `scan-field`。

三者共同锚在**「真实需求」**上:blueprint 写它,cut-scope 拿它对内砍,scan-field 拿它对外比。

## 2. 插件形态

- **插件名**:`true-north`(真北 = 不被实现细节 / 沉没成本 / 从众带偏的方向锚)。
- **三个 skill**,全部 stack-independent、纯手动触发、不装 hook:
  | skill | 方向 | 触发时机 | 是否改文件 |
  |---|---|---|---|
  | `living-blueprint` | 记录(源) | 项目早期建、演进中更新 | 改 BLUEPRINT.md |
  | `cut-scope` | 对内剪枝 | 多轮 superpowers 后手动 | **只读**,只给方向 |
  | `scan-field` | 对外扫同款 | 项目完工后手动 | 只产出对比文档 |
- **不并入 vibe-\***:vibe-scripts/vibe-apps 是 Python 专用脚手架(纵轴、绑栈);true-north 是与栈无关的设计过程(横轴)。不同轴,不合并。vibe-* 留在 xu-skills。

## 3. 三个 skill 细节

### 3.1 living-blueprint(照搬 PR #1 版,不改)

即 xu-skills `feat/living-blueprint` 分支(PR #1)里的成品:一份永远当前、**只讲功能不讲实现**的 `docs/BLUEPRINT.md`(五节:一句话 / 功能与行为 / 边界·明确不做 / 硬约束+重构自由声明 / 功能痛点)。两条承重:行为契约 + 硬约束/自由声明分离。更新纯手动、覆盖式。

**关键:它已引入 subagent**(见 §4)。true-north 直接接收这个成品,内容不动。

### 3.2 cut-scope(新)

- **目标**:对一个已被 superpowers 打磨多轮、开始膨胀的项目设计,做**方向性剪枝**。
- **输入**:该项目的 BLUEPRINT.md / spec / 对话 transcript + 当前代码。
- **动作**:
  1. **冷眼确立真实需求**(subagent,见 §4)——**有 BLUEPRINT.md 就核对**它记的意图 vs 已膨胀的设计/代码、找出漂移;**没有就从 spec/transcript/代码重建**。全程不被「已经建了这么多」的沉没成本绑架。
  2. 逐项标出**疑似过度工程 / 偏离真实需求**的部分,给出「留 / 砍 / 降级」的方向建议 + 理由。
  3. 回主线,**跟用户交互确认真实需求锚点**,再呈现剪枝清单。
- **红线**:**只纠正方向,不改任何文件**。产出是一份建议,改不改、怎么改由用户后续决定(可能接 superpowers 或直接改 BLUEPRINT)。
- **借鉴 Ponytail**:可复用它的极简阶梯作为「这块是不是过度」的判据(需不需要存在→是否已在别处→stdlib/native→现有依赖→一行→最小代码),但**判据服务于「对齐真实需求」,不是无脑砍代码行数**。

### 3.3 scan-field(新)

- **目标**:项目完工后,扫市面同款,产出**对比 + 升级方向**文档,喂给下一轮迭代。
- **范围**:广义「更好的方案」,不止运行时性能——思路、架构、生态位、能抄的好点子都算。
- **输入**:该项目的 BLUEPRINT.md(是什么、给谁、解决什么)作为搜索锚。
- **动作**:
  1. **研究 fan-out**(subagent,可并行多源,见 §4)——搜 GitHub / 插件市场 / web,各自回摘要。
  2. 主线汇总成**原创度对比表** + **未来升级方向(按优先级)** + **判断准则** + **Sources(带日期)**。
- **产出模板**:直接沿用 `docs/2026-07-02-生态对比与升级方向.md` 的结构:
  - 对比表列:`自制 | 市面同款 | 原创度(🔴红海/🟠撞款/🟡邻近/🟢原创) | 差异点·我独有`
  - 升级方向按优先级:🔴 去红海抄思路 / 🟠 站肩膀差异化 / 🟢 继续深耕真差异
  - 判断准则:「重写前先看过同款;真正的浪费只有一种:不知道同款存在」
- **红线**:只产出文档,不改项目代码/设计。

## 4. subagent 策略(两种范式)

三个 skill 都用 subagent,但**动机不同**:

- **living-blueprint = 防实现泄漏的防火墙**(已实现):刚泡完实现的主 agent 会把 how 漏进 what;派 fresh subagent 冷眼蒸馏,顺带消化大 transcript。三源并用(蓝图基底 + transcript 意图源 + 代码现实源)、三条死命令(只写可观察行为 / 只收拍板意图弃废案 / 覆盖式对账标缺口)、graceful 缩放(transcript 不在就退化,小改 inline)。
- **cut-scope = 防沉没成本的防火墙**(借 living-blueprint 同一范式):主 agent 对自己加的每块有依恋、会替过度工程辩护;fresh subagent 无依恋才砍得下去。三源、缩放照搬。**差别**:多一步「跟用户确认真实需求锚点」,那步留主线,不进 subagent。
- **scan-field = 研究 fan-out**(不同范式):subagent 是为把 web 搜索的噪音关在一次性上下文里、主线只收对账表;对应 superpowers `dispatching-parallel-agents`,可并行多源。

## 5. 与 superpowers 共存

altitude 分层:superpowers 在**构建流程层**(brainstorm→plan→execute→review→finish,自动流),true-north 在**设计/意图层**(手动反思,锚真实需求)。共享接口 = `BLUEPRINT.md`(blueprint 写,cut-scope/scan-field 读)。

| true-north | 挂在 superpowers 哪 | 会不会撞 |
|---|---|---|
| living-blueprint | brainstorming/execute 完 → 蒸馏「当前全貌」进 BLUEPRINT.md(what);spec/plan 管 how | 不撞:坐其上,一处 what 一处 how |
| cut-scope | ≠ brainstorming 的当场一次性 YAGNI;它是事后、可反复、只读、锚真实需求的独立审计 | 不撞:不同时机/权限 |
| scan-field | ≠ finishing-branch 的「并分支」;它是完工后向外反思 | 不撞:不同关注点 |
| cut-scope/scan-field | ≠ `/code-review`·`/simplify`(审代码) | 不撞:它俩审设计/市面,高一层 |

**共存的根本保证**:true-north 全手动、cut/scan 只读、**不装任何 hook** → 不介入 superpowers 自动流,只是插在其生命周期不同点上的手动锚。

## 6. 打包与迁移(方案 B)

- **落地位置**:`plugins-dev/true-north/`,独立 git 仓推 `patrick1099` 的独立 GitHub 仓库(遵循 plugins-dev 每插件单独仓的约定);在根 `plugins-dev/.claude-plugin/marketplace.json` 的 `plugins` 数组加一行注册。
- **living-blueprint 迁移(方案 B)**:**不 merge xu-skills PR #1**,直接把 `feat/living-blueprint` 分支里的 `skills/living-blueprint/SKILL.md`(及其配套)挪进 `true-north/skills/living-blueprint/`;xu-skills 那个 PR **关闭**(注明设计已迁往 true-north)。xu-skills 里对 design-journal 的引用(vibe-apps「必用」、vibe-scripts「建议用」的 Referenced-by)改指向 true-north 的 living-blueprint。
- **plugin.json**:name=`true-north`,三个 skill 各一个 `skills/<name>/SKILL.md`。
- **提交身份**:`patrick1099`(plugins-dev 目录已配好个人身份)。

## 7. 非目标 / 暂不做

- 不做自动 hook(核心诉求就是手动)。
- cut-scope / scan-field **不改项目文件**(只给方向 / 只产文档)。
- 不做 xu-skills 的整体重组(vibe-* 是否再拆分等)——单独任务,本次不碰。
- 不把 Ponytail 的 audit/review 原样搬进来——只借「极简阶梯」判据思路,不复制其自动注入行为。

## 8. 待办(交给 writing-plans)

1. 建 `true-north/` 骨架(plugin.json + 三个 skills 目录)。
2. 迁 living-blueprint(方案 B:从 PR 分支挪内容,关 PR,改 xu-skills 引用)。
3. 写 cut-scope SKILL.md(含防沉没成本 subagent 范式 + 交互确认锚点 + 只读红线 + Ponytail 阶梯判据)。
4. 写 scan-field SKILL.md(含研究 fan-out subagent + 2026-07-02 对比文档模板 + 只产文档红线)。
5. 根 marketplace.json 注册 + 独立仓推送。
6. 各 skill 自测(参照 superpowers writing-skills)。
