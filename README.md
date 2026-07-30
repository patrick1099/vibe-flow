# vibe-flow

一套**完整但不重**的个人 vibe-coding 工作流。

> 先明确需求，再判这是小事还是大事：**小事要省，大事要好。**

省的是流程，不是质量；好的是该厚的地方厚，不是每次走满。重流程框架的病不是"太严谨"，是**只有一档**——所有事一律走满。这套东西的承重设计就是**有档位**：入口 skill `vibe-flow` 判一次档，澄清厚度、探不探方案、建不建文档、实现纪律、验证强度、收工后要不要回头，全是这一次判定的下游。

## 七个 skill

| skill | 环节 | 触发 | 是否改文件 |
|---|---|---|---|
| `vibe-flow` | 总入口：判意图 → 判档 → 路由 → 决策边界 → 验证收尾 | 建/改/扩一个脚本、工具、应用、功能 | 只改你要它改的 |
| `clarify-needs` | 明确需求：把目标 / 方案 / 偏好 / 约束分开 | **纯手动**（`disable-model-invocation`） | 写 `docs/NEEDS.md` |
| `living-blueprint` | 留意图：只讲功能不讲实现的当前全貌 | 手动，长期项目 | 写 `docs/BLUEPRINT.md` |
| `vibe-scripts` | 实现：独立 Python 脚本的四层五区 + 分级 | 写/改独立脚本前 | 写脚本 |
| `vibe-apps` | 实现：带界面 / 要分发的 Python 应用五层 | 搭应用脚手架前 | 写应用 |
| `cut-scope` | 回头剪枝：冷眼核对真实需求 vs 已膨胀的设计 | 手动，迭代多轮后 | **只读**，只给方向 |
| `scan-field` | 回头扫同款：原创度对比 + 升级方向 | 手动，做到能用之后 | 只产对比文档 |

## 档位怎么判

**默认省档；升到好档必须说得出理由。** 命中任一即好档：

- **会再用**——不是跑完即弃
- **不可逆**——删除 / 覆盖 / 迁移数据 / 联网上传 / 发出去收不回
- **给别人**——要分发，或别人会依赖它
- **跨会话**——一次做不完
- **多目标纠缠**——两个以上独立目标或用户

这五条**故意都是不必深挖需求就能知道的外部事实**，所以判档不用等澄清做完。

**你一句话可以直接定档**，优先于以上判据："这个随便做一下" → 省档；"这个要做好" → 好档。

## 环节与档位对照

| 环节 | 省档（默认） | 好档 |
|---|---|---|
| 开工前 | 查有没有现成的 | ＋轻扫市面同款 |
| 明确需求 | 不澄清，或只问一个问题 | 挖目标 / 分清偏好与约束 / 翻译验收 |
| 探方案 | 不探，直接做 | 多条路时给 2–3 个方案 + 取舍，你拍 |
| 实现 | 最小可用，禁套架构 | 按分支的完整纪律 |
| 留文档 | 不建 | `NEEDS.md`；长期项目上 `BLUEPRINT.md` |
| 验证 | 代表性输入跑通 | 按交付形态实际使用 ＋ 针对性测试 |
| 收工后 | 无 | 膨胀了剪枝 / 完工了扫同款 / 更新蓝图 |

**不命中的环节完全不提。** 这是路由图，不是阶段清单——把它当必经阶段依次跑，就退回了它要取代的那种流程。

## 与重流程框架的关系

不装 hook、skill 之间不自动串联、`clarify-needs` 连模型调用都关了。需要正式 spec/plan 落盘再按计划执行（brainstorming → writing-plans → executing-plans）、TDD、工作树、并行子代理这类重仪式时，手动去调 [superpowers-manual](https://github.com/patrick1099/superpowers-manual) 那套；**本工作流不依赖它，没装也能走完全程**。

## 安装

```
/plugin marketplace add patrick1099/vibe-flow
/plugin install vibe-flow@vibe-flow
```

入口是 `vibe-flow`；`clarify-needs` / `cut-scope` / `scan-field` / `living-blueprint` 只在你显式调用时才跑。

## 沿革

本插件由两个前身合并而成（2026-07-30）：`vibe-flow` / `vibe-scripts` / `vibe-apps` 原在 [xu-skills](https://github.com/patrick1099/xu-skills)，`clarify-needs` / `living-blueprint` / `cut-scope` / `scan-field` 原是 [true-north](https://github.com/patrick1099/true-north) 四件套。合并理由与档位设计见 `docs/history/2026-07-30-vibe-flow-plugin-merge.md`；更早的设计记录见 `docs/history/` 其余文件，`clarify-needs` 的 RED 基线与夹具见 `docs/evals/`。
