# vibe-flow 插件合并记录

> 日期：2026-07-30
> 状态：已落地
> 一句话：把散在 xu-skills 与 true-north 的 7 个 skill 收成一套有档位的完整工作流，入口 `vibe-flow`。

## 1. 起点

起点是一个包装问题："true-north 是不是可以和 vibe-* 合并？script-manager 是不是也可以？"

第一轮结论是**不合并**——2026-07-07 的 `2026-07-07-true-north-design.md` §2 判过：vibe-scripts/vibe-apps 是 Python 专用脚手架（纵轴、绑栈），true-north 是与栈无关的设计过程（横轴），不同轴不合并。这条理由本身没错。

但用户随后把问题重新框定了：**"这些 skill 已经能凑成一套工作流了，vibe-flow 开始，只是不像 superpowers 那么重。"** 这不是包装问题，是**组合**问题——一旦按工作流看，边界该按"是不是同一条链路"切，而不是按"绑不绑技术栈"切。原判据（轴向）回答的是"要不要放一起讲"，新判据（链路）回答的是"用户是不是一次要用它们全部"。后者胜出。

## 2. 真正的设计增量：一个显式档位

合并本身只是搬家，不值得开新仓。值得的是用户那句**"明确需求，小事要省，大事要好"**：

- "明确需求"是**前置**，不是第一道工序——不明确需求就判不出大小，也不知道"好"指什么。
- "小事要省 / 大事要好"是**同一个旋钮的两端**。

对照旧 vibe-flow 发现：它其实**已经有三处缩放判据，但是散的、各说各话**——§3 "清楚且小、可逆 → 直接做"、§4 "文档按生命周期"、§7 "验证按风险"。三处各判一次、判据还不一样，结果这个档位从未成为一等公民：完全可能澄清阶段按小事、验证阶段按大事。

所以新入口的承重设计是：**需求明确后判一次档，全流程沿用同一档。** 澄清厚度、探不探方案、建不建文档、实现纪律、验证强度、收工后回不回头，全是这一次判定的下游。

### 关键设计决定

1. **默认省档，升档要理由**（不对称是故意的）。省是默认路径，厚必须说得出命中哪条判据。
2. **升档判据全部选"不必深挖需求就能知道的外部事实"**：会再用 / 不可逆 / 给别人 / 跨会话 / 多目标纠缠。这样判档就不必等澄清做完，破掉"要澄清才能判档、要判档才知道澄清多厚"的循环。顺序是：粗判 → 按档澄清 → 事实变了就升档（**只升不降**）。
3. **用户一句话直接定档，优先于判据。** 安全阀：判错档的代价是双向的（小事判成大事 = 退回重流程；大事判成小事 = 交付不及格），所以档位必须用户可见、可一句话推翻。
4. **总图是路由图，不是阶段清单。** 不命中的环节一个字都不该出现。反模式里明写"把总图当必经阶段依次跑"。

## 3. 边界：收什么、不收什么

**收（7 个，构成完整链路）**：vibe-flow（入口/判档）、clarify-needs（明确需求）、living-blueprint（留意图）、vibe-scripts + vibe-apps（实现两分支）、cut-scope + scan-field（回头两动作）。

**不收 `script-manager`**（留在 `$CLAUDE_HOME/skills/`）：它是**登记册 + 脚本本体**，装的是本机数据（个人脚本清单、`%LOCALAPPDATA%\Programs\bin` 的 shim 路径），不是方法论。塞进公开插件会同时踩三个坑——公开个人脚本清单与本机路径、每登记一个新脚本就要 bump 版本、而它本就是"纯本机不开仓库"那档。**但它指向的反射是真的**：整条链路原先没有一句"先查有没有现成的"。改为在 `vibe-flow` §3 加一步开工前复用检查（引用 script-manager 的 INDEX，装了才有），把反射写进流程、把数据留在本机。

**不收 `superpowers-manual`**，三条理由（第二条是硬的）：

1. **定位自毁**：vibe-flow 存在的理由就是取代"每次走满"的那套。把被取代者装进取代者，用户装一个 vibe-flow 会连带拿到 14 个重流程 skill（962K），那正是要摆脱的东西。
2. **它是上游 fork，融合即断更**：superpowers-manual 追 obra/superpowers 6.1.1，靠 `UPSTREAM.md` + `scripts/apply_manual_policy.py` + `tests/test_manual_policy.py` 机械同步上游。并进来这条线就断了，且不可逆。
3. 体量不对等：14 个重 skill vs 7 个薄 skill。

**但接缝是真的**：clarify-needs 原写着"brainstorming 是它的可选前置"，living-blueprint 有一整节「与 superpowers brainstorming 的接缝」，cut-scope 的触发条件写的是"多轮 superpowers 后"。一个自称完整的工作流，方案探索那一环是外包的。**修法不是搬进来，而是让好档路径自带一个薄的探方案**（§4：一条明显路就不探；涉及数据模型/持久化/主流程给三点短设计；真有 2–3 条各有取舍的路才并排给方案让用户拍），并留一句可选出口：要正式 spec/plan 就手动调 superpowers-manual，**本流程不依赖它**。

## 4. 顺带修掉的一个真 bug

旧 vibe-flow §3 写"调用 `true-north:clarify-needs` 做厚澄清"，但 clarify-needs 的 frontmatter 是 `disable-model-invocation: true`——模型**不能**用 Skill 工具启动它（2026-07-16 真机冒烟已验证，模型亲口报"标了 disable-model-invocation 不能用 Skill 工具启动"）。这条路由一执行就卡住或被含糊绕过。改为：提示用户手动调 `/vibe-flow:clarify-needs`，用户不想调就按好档问法自己问、不卡住。反模式新增一条"声称自己能启动 clarify-needs"。

## 5. 落地动作

- 新仓 `$VAULT/shared/plugins/vibe-flow`，公开仓 `github.com/patrick1099/vibe-flow`，自成市场 `vibe-flow@vibe-flow`。
- `xu-skills` 删 vibe-flow / vibe-scripts / vibe-apps（连带 `docs/vibe-apps-栈权衡与改进候选.md` 迁走），留 learning×2 + curating-memory + skill-review。
- `true-north` 仓保留但退役：README 改为指向新仓，从本机 enabled 列表移除。四个 skill 的活源自此在新仓。
- 迁入时统一去掉 `true-north:` 前缀（同插件内直接写 skill 名），并把 5 处"默认走 superpowers"的措辞改成"本插件自洽 + superpowers-manual 可选"。
