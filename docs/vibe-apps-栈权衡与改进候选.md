# vibe-apps 栈权衡 & 改进候选（决策笔记）

> 状态：**决策输入，未定案，未改任何 skill 文件。** 记录 2026-07-07 一场从
> "vibe-scripts 和 vibe-apps 是否功能重合" 展开的讨论 + 实测数据，供后续决定
> 要不要动 `skills/vibe-apps/SKILL.md`。

## 0. 缘起与第一个结论：两个 skill 不重合

问题起点："vibe-scripts 和 vibe-apps 功能是否重合？"

结论：**不是功能重合，是同源。**
- 路由**互斥且双向交叉引用**：有界面/要分发(exe)/可能变网站 → vibe-apps；否则(命令行单文件) → vibe-scripts。一个项目只落一个。
- **skill 的 `description` 本身就是路由器**——匹配发生在加载正文之前、免费。两个窄 description 比一个宽 description 路由更准。
- 真正重复的只有 ~10 行**共享 DNA**：Core 纯逻辑不做 IO、依赖方向 App→Core、配 living-blueprint 记功能蓝图、省 token 原理。
- 合并（router+两分支 / 扁平单文件）是"牺牲路由精度 + 增加加载成本"换"消除 10 行重复"，不划算。若要动，唯一合理动作是把共享 DNA 抽成一份 reference 或并入 true-north:living-blueprint。

## 1. 核心模型：三角 + 第四轴

桌面小工具选栈，本质是**三选二的三角**，外加一根后补的轴：

```
        体积小
        /    \
   快启动 ──── 易调试/迭代
```
- **第四轴：UI 好看度 + AI 设计助力** —— 见 §4，实质是"前端锁 HTML"的强力砝码。

没有任何一个栈同时拿满三角。选栈 = 给"我这工具最不能放弃哪一角"投票。

## 2. 实测数据（本机，2026-07-07）

demo：`C:\Users\huawei\Desktop\vibe-app-demo`（文本工具箱，走标准 vibe-apps 五层）。
环境：Win10 + Defender，Python 3.14，fastapi 0.139 / pydantic 2.13(+pydantic_core 2.46) /
uvicorn 0.50 / pywebview 6.2 / pyinstaller 6.21 / UPX 4.2.4。

| 打包方式 | 体积 | 启动到可用界面(health 代理) | 备注 |
|---|---|---|---|
| onedir + UPX | 文件夹 18.3MB(158 files) / **zip 14.3MB** | ~1.88–2.48s，稳态 **~1.9s** | 无解压环节 |
| onefile + UPX | **单 exe 14.4MB** | ~2.28–2.63s，**~2.4s** | 每次启动解压到 %TEMP% |

- core 单测 pytest 6 passed；HTTP 端点(stats/base64/case/静态)全部核验通过。
- splash 首帧几百 ms 可见；上表是"切到真界面"的时间。

## 3. 被实测打脸的两个判断（务必记住，别重犯）

拍脑袋估计错了两次，实测纠正：

| 我之前说 | 实测 | 纠正 |
|---|---|---|
| onedir 能到 ≤1s | ~1.9s | **启动是 import-bound**：FastAPI+pydantic_core+uvicorn 的 import 就 ~1.9s，UPX/onedir 动不了它 |
| onefile 是 3s 大税、要避开 | 只比 onedir +0.5s | **解压税与包大小挂钩**：14MB 小包上很便宜；多秒级恐怖故事是给几百 MB 大包(numpy/torch)+激进杀软的 |

坐实的两条：
- ✅ 体积能压到 ~14MB（onedir zip 与 onefile 几乎一样，因 onefile 内部也压缩）。
- ✅ **"砍依赖"是唯一同时改善体积+启动的 Pareto 杠杆**——被 ~1.9s import 地板反向坐实。

**小工具实操含义**：onefile 单文件方便、体积≈、只多 ~0.5s，**对小自用工具反而更划算**（推翻我之前"避开 onefile"的强硬立场）。onedir 的价值在包变大时才凸显（解压税随体积膨胀）。

## 4. 完整栈对照地图

数字除 pywebview 行外均为**估计**（含高确定度的结构判断）。

| 栈 | 语言 | UI 技术 | 体积 | 启动 | 调试/迭代 | 变网站 | UI好看+AI助力 |
|---|---|---|---|---|---|---|---|
| **pywebview**(实测) | Python | HTML/JS+系统 webview | 14.3MB | ~1.9s | ✅✅ 浏览器 devtools | ✅ 换交付层 core 不动 | ✅ |
| PySide6+QML | Python | QML+Qt 运行时 | ~35–60MB | ~1s | ~ QML 热重载，丢 devtools | ❌ | ❌ |
| C++ Qt6+QML | C++ | QML+Qt 运行时 | ~25–40MB | ~0.3s | ❌❌ 编译周期+C++坑+GB级SDK | ❌ | ❌ |
| **Tauri** | Rust | HTML/JS+系统 webview | ~5–10MB | ~0.3s | ❌ Rust 税(前端可 devtools) | ~ 前端复用/后端重写 | ✅ |
| **Rust+Slint** | Rust | .slint+自带渲染 | ~8–20MB | ~0.2s | ❌ Rust 税(.slint 有热重载) | ~ 有 WASM 但非 DOM 站 | ❌ |

关键洞察：
- **"C++/Rust = 小" 是错觉**——吃体积的是 UI 运行时。Qt 自带渲染器 → 胖；pywebview/Tauri 借**系统 webview** → 瘦（pywebview 14MB 能赢 Qt）。
- **Slint 是"小+快"极致答案**：连 webview 依赖都去掉，真单文件、可下探嵌入式；账单还是 Rust 调试/迭代税。

## 5. "UI 好看 + AI 助力" 如何收窄选择

- **HTML 做好看确实最强**：CSS 是地表最强样式系统；设计生态(Tailwind/shadcn/Pico/图标/字体)碾压。
- **AI 生成 HTML >> 生成 QML/.slint**（web 前端是训练数据最多的 UI 代码）；"AI 设计 UI"整波工具(v0/Claude Artifacts/bolt/screenshot-to-code)**全是 HTML 系**，无 QML/Slint 对应物。
- **这是给"HTML 前端"投票，不是给某后端投票**：pywebview 和 Tauri **都**吃这份红利 → 只淘汰 Qt/Slint，**决不了 pywebview vs Tauri**。

⟹ **好看优先 → 前端锁 HTML → Qt/Slint 出局 → 只在 pywebview(Python，易调/可变网站/~2s) 与 Tauri(Rust，小快/难调) 间选后端语言。**

## 6. 给 vibe-apps 的改进候选（均未采纳）

1. **"反 Rust/Tauri" 换硬理由**：现文案挂在"换语言=core 要整个重写=永远贵"这根柱子上；而
   - living-blueprint 记录活蓝图（What）后，"重写成本"被削弱（不再逆向猜代码）；
   - 更抗打的柱子是 **调试/迭代税永久偏高 + (HTML 前端的好看+AI 生态)**。
   建议把理由从"重写成本"改挂到"调试税 + 好看/AI 生态"。
2. **补 onefile vs onedir 指引**：小包默认 **onefile**（单文件方便、体积≈、+0.5s）；仅当包变大(重库)才 onedir 避解压税。
3. **补"启动敏感 → 轻依赖档"提示**：Python 启动地板 ~1.9s 源自 FastAPI+pydantic import；真在乎启动可考虑裸 Starlette / stdlib（**未实测，预测 ~1s**，见 §7）。
4. **HTML 前端理由升级**：把"好看 + AI 设计生态(v0/Artifacts/shadcn/Tailwind)"写成选 HTML 的现代硬理由（比现有的"零构建+可调"更有说服力、且随 AI 生态增值）。
5. **React 档张力（待定）**：最强 AI 设计工具是 React+Tailwind+npm，与 vibe-apps"零构建无 npm"冲突；纯 HTML 的 AI 生成仍好用(Tailwind 可走 CDN)，但够不到 shadcn 那批组件级工具。是否给 vibe-apps 留"React 档"待定。
6. **明确邻栈边界**：Qt/Slint/Tauri **不是 vibe-apps 变体**，是"离开 Python 时"的邻栈。可在 skill 加一句"何时该离开 vibe-apps"的边界说明 + 指向本表。

## 7. 未决 & 未做

- **pywebview vs Tauri**：后端 Python(好调/可变网站) vs Rust(小快/难调)——按具体工具"最不能丢哪一角"定，未定。
- **轻依赖档实测**：裸 Starlette/stdlib 版是否真能把 ~1.9s 拉到 ~1s、zip 再掉一两 MB——**预测未验证**，可再打一次对照。
- **是否真的动 skill**：**已定，见 §8。** 结论：不建迁移 skill，只写本决策记录 + vibe-apps 一处精度修。

## 8. 分发 & Rust 迁移的决策（2026-07-07 定稿）

承接 §6#1/#6 那批候选。一场从"前后端已分离 → Tauri 好接入"展开的讨论，落定了一套"如何架构成通往 Rust/Tauri 的坡道"的决策。

### 8.0 为什么最终**不**建 skill（RED 证据）

曾打算把"分发 / 毕业 Tauri"独立成 skill `python-rust-escape`。按 `writing-skills` 铁律先跑基线：**2 个无 skill 的 fresh agent**，面对"分发我的 pywebview 应用、要不要上 Tauri/Rust"，**都自发给出正确答案**——"别重写、打 exe、optimize the packaging story not the language"，其中一个还自推出了"面子 vs 实质"论证和 onedir 更快启动那条。

→ 对照组没暴露失败 = skill 的核心闸门（"别过度热情推 Tauri"）教的是 **agent 本就会的事** → **不建 skill**（撞"别盲目造轮子"）。剩下真正非显然的**架构决策**沉淀为本节 doc。（n=2，但两个都干脆一致，信号足够停手重估。）

### 8.1 双轨定性：不是"两套平等框架"，是"Python 主场 + Tauri 发布靶子"

终局设想：vibe-apps 搭框架 → 平时在 Python 版开发/调试（迭代快、devtools、pytest，**这是最看重的一角**）；**假如**产生分发需求，再维护一个 Tauri 版。

关键是把关系读对——**不对等**：
- **Python 版 = 主场**：所有开发/调试/pytest 在此发生，权威副本。
- **Tauri 版 = 发布靶子**：从共享件**重新生成**的分发构建，不在里面"住"，只在发版时 build。

这么定性，"维护两套"的恐惧就退成"一个开发框架 + 一个大部分可再生的发布产物"，Tauri 独占的手工维护只剩薄 axum 壳。

### 8.2 两套之间什么共享、什么重复（决定双轨可不可行）

| 层 | Python 版 | Tauri 版 | 共享? |
|---|---|---|---|
| `web/` HTML/CSS/JS | localhost HTTP | localhost HTTP | ✅ **一份逐字共享** |
| **core（若 Rust/PyO3）** | import `.pyd` | 链接 crate | ✅ **同一份 Rust 源** |
| core（若 Python） | 直接用 | 用不了 → Rust 重写 | ❌ **双语言手工对齐（地狱）** |
| `api/` 薄适配 | FastAPI 路由 | axum 路由 | ❌ 两份，但薄 |
| 壳 | pywebview+PyInstaller | Tauri | ❌ 两份，但 boilerplate |

**结论**：双轨可行**当且仅当 core 是 Rust**——那两套就共享 web + 共享 core（最贵两块），只剩薄 api 壳重复。core 若是 Python，Tauri 版要把业务逻辑用 Rust 重抄并手工同步 = 真正的噩梦。这张表直接坐实"能用 Rust 写的模块直接 Rust 写"是让双轨从地狱变可行的开关。

### 8.3 Rust 的**时机**纪律（别 upfront）

"能用 Rust 写"这张网太大（几乎任何纯函数都能），而每个 Rust 模块都在开发循环塞一道 maturin 编译、并砍掉"易调试"那一角。分发又是**条件性未来**（"假如"）。所以：

- **默认全 Python**：迭代/调试拉满；core 保持无状态模块化 = 换 Rust 的门**零成本常开**（PyO3 期权白持有，没必要现在行权）。
- **只有一种早写 Rust**：第一天就确定"**既是热点、又一定被 Tauri 后端复用**"的耐用件（协议编解码/校验/核心算法）。写一次两轨共享 = DRY，不是过早。
- **其余等分叉**：真到要 Tauri 那刻，再把 core 逐模块 PyO3 转。诚实代价：会有一坨集中移植，但那时**已知工具真身**，比 day-1 瞎猜哪个模块值得强得多。

### 8.4 分发三档（别一有分发念头就跳 Tauri）

- **档 0（默认，覆盖多数）**：`PyInstaller` 打 Python exe 直接给。一套框架。基线 agent 自发落在这档。
- **档 1（面子/启动真招人烦才上）**：受众吃那份精致、或 2s 冷启动真烦人 → 才从共享件立 Tauri 发布靶子。
- **Tauri 到底买什么**：主要是**面子**（体积 ~5–10MB、原生感）；**唯一实质例外＝砸穿 ~1.9s 启动地板**（丢掉整张 FastAPI+pydantic import 图 → ~0.3s）。**PyO3 对启动毫无帮助**（core 换 Rust，FastAPI/pydantic 照样 import；pydantic_core 本就是 Rust）。启动这条另两个解：轻依赖档（§7，预测 ~1s 未验）或 Tauri。

### 8.5 PyO3/maturin 机制 + 活样板

- **PyO3** = Rust↔Python 桥：Rust 写模块编成 `.pyd`/`.so`，Python `import` 无感调用；**maturin** = 配套构建器（`maturin develop`/`build`）。
- **活样板 = `pydantic_core`**：pydantic v2 就是把 v1 纯 Python 校验热点用 PyO3 换成 Rust、Python API 一字不变——也正是拖慢我们 ~1.9s 启动、且 Nuitka 编译不动的那个 `.pyd`。它本身就是"Python 核心逐模块迁 Rust 且调用方无感"的成品。
- **Nuitka**（编译器，非打包器）：能编纯 Python import 那片，但砍不动已是 Rust 扩展的 pydantic_core → 对我们那 ~1.9s 地板大概率**部分胜、砸不穿**，还吃"迭代"那一角（分钟级 C 编译 + 工具链）。不是银弹。

### 8.6 已落地的改动

- **vibe-apps `换零件规则`**：把"→Rust=永远贵、core 整个重写"改成"kept-clean core 可 PyO3 **逐模块**迁、耐用件可早写 Rust"，指回本节。
- **未加**"第三 payoff"注解（前端可搬 Tauri / core 可 PyO3 化）到 vibe-apps 各铁律——避免 skill 变胖，且不改行为；理由留在本 doc。
- `禁止 Tauri/Rust` / 反模式"为了小体积上 Tauri/Rust" **保持不变**——"别从 Tauri **起步**"与"若后来要迁则是增量"不矛盾，无需改。
