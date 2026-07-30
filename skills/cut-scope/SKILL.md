---
name: cut-scope
description: Use when a project has been through several rounds of iteration and its design has bloated, and you want a manual, read-only pruning pass that re-anchors on the TRUE requirement and flags over-engineering as direction-correction — 手动剪枝项目设计、对齐真实需求、砍过度工程、只给方向不改文件、防沉没成本。仅由用户显式请求触发(剪枝/精简我的项目设计、这块是不是过度了)。只读,不改任何文件。Stack-independent.
---

# cut-scope：对内剪枝，锚回真实需求

## 总纲

> 项目被打磨多轮后会膨胀（无论是 vibe-flow 好档反复迭代，还是走了 superpowers 那类重流程）。cut-scope 冷眼核对「真实需求 vs 现有设计」，把过度工程 / 偏离需求处标成方向建议——**只纠偏，不改文件**。

## 何时用 / 不用

- **用**：一个已迭代多轮、开始有「这块是不是不用做」感觉的项目设计。
- **不用**：还在首轮探方案时（那时用 `vibe-flow` §4「v1 明确不做什么」就够）；跑完即弃的微脚本。

## 与邻居划界

- ≠ 探方案时的当场一次性 YAGNI：cut-scope 是**事后、可反复、只读**的独立审计。
- ≠ `/code-review`、`/simplify`：它们审**代码**；cut-scope 审**设计 / scope**，高一层。
- 输入锚 = living-blueprint 的 `docs/BLUEPRINT.md`：**有就核对，没有就从 spec/transcript/代码重建**。

## 铁律：只读

cut-scope **不编辑任何项目文件**。产出是一份「留 / 砍 / 降级」建议清单，交给用户；改不改、怎么改由用户决定（手动改 BLUEPRINT，或接 `superpowers-manual` 那套重流程）。

## 流程

1. **冷眼确立真实需求**（subagent，见下）。
2. **逐项判过度工程**（Ponytail 极简阶梯作判据）。
3. **回主线跟用户确认真实需求锚点**，再呈现剪枝清单。

## subagent：防沉没成本的防火墙

刚跑完多轮的主 agent 对自己加的每块有依恋、会本能替过度工程辩护。派一个 **fresh subagent** 冷眼评估——它没依恋，才砍得下去。

**三源并用**：`BLUEPRINT.md`（意图基底）+ transcript / spec（真实需求源）+ 当前代码（现实源：实际建了啥）。

**subagent 死命令**：①先用一句话复述真实需求，作为砍的标尺；②逐项给「留 / 砍 / 降级 + 一句理由」，理由必须挂回**真实需求**或**极简阶梯**，不空谈「简洁」；③只产建议、不碰任何文件；④对话中途被否的废案不算需求。

**缩放 / graceful**：文档少就主线直接读、不必起 subagent；文档 / transcript 又大又吵才起 subagent 一次性消化。交互确认锚点那步**始终留主线**（要跟用户对话），不进 subagent。

## 判据：Ponytail 极简阶梯（服务于对齐需求，不是无脑砍行数）

逐块问：**需不需要存在**（对真实需求有用吗）→ **是否已在别处有了** → **stdlib / native 够不够** → **现有依赖能否覆盖** → **能否一行 / 最小实现**。任一层能满足就标「砍 / 降级」。判据永远服务于「对齐真实需求」，砍的是偏离需求的过度工程，不是为减行数而减。

## 产出格式

```markdown
# <项目> cut-scope 剪枝建议 (日期)
真实需求(一句话锚)：…
| 设计块 | 判定(留/砍/降级) | 挂回哪条需求/阶梯 | 理由 |
|---|---|---|---|
| … | 砍 | 需求无此项 | … |
建议下一步：(哪些交给用户改——不代改)
```

## 反模式

- 动手改文件（越界，只该给方向）
- 不先确立真实需求就开砍（砍成什么样没标尺）
- 用「感觉复杂」当理由（要挂回真实需求或极简阶梯）
- 被沉没成本说服「都建了就留着」（正是要 fresh subagent 冷眼的原因）
- 把它当 `/simplify` 用去抠代码（它审的是设计 / scope）
