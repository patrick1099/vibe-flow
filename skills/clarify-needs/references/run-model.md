# 运行模型图：把"我理解的"画出来给用户挑错

> **为什么有这一步**：一句话的需求锚颗粒度太粗——"出错了怎么办、哪一步要用户介入、最后产出长什么样"全藏在大白话底下，等代码写完才暴露分歧。画成图，每个分岔、每个出口都得落一个框，**我没想清的地方躲不掉，用户没说的地方一眼看见**。

## 两层图，放在两个地方

| 层 | 画什么 | 在哪画 | `--layer` |
|---|---|---|---|
| **第一层：它跑起来是什么样** | 用户视角：谁触发 → 每步发生什么 → 分岔 / 出错走哪 → 最后用户拿到什么 | clarify-needs（锚完真需求之后） | `run` |
| **第二层：我打算怎么搭** | 模块怎么分、数据从哪来到哪去、存在哪 | `vibe-flow` §4 探方案 | `build` |

第一层**不许出现实现**（没有函数名、库名、模块名）——那是需求，不是方案。第二层才讲怎么搭，但仍是**让用户知道我会怎么做**，纯技术内部选择照旧不许反问用户（vibe-flow 的决策边界不变），`guess` 只标会改变用户体验或数据的点。

## 两种画法，按图的性质选

| 图靠什么表达 | 例子 | 源文件 | 为什么 |
|---|---|---|---|
| **连线**：先后、分岔、出错走哪 | 运行流程、数据流 | `.d2` | D2 自动排版，改一个框只改一行 |
| **嵌套与对齐**：谁在哪一层、谁包含谁 | 分层架构、系统框架（APP / Driver / HAL / BSP 那种） | `.html` 片段 | 格子要精确对齐，D2 的自动布局摆不出来 |

第一层几乎总是流程 → `.d2`。第二层看情况：讲"数据怎么流"用 `.d2`，讲"模块分几层、各层有什么"用 `.html` 片段。拿不准就问自己：**去掉所有箭头，这张图还剩下意思吗？** 剩下 → 分层结构；不剩 → 流程。

## 什么时候画

- **画**：要做的东西有**流程**——多步、有分岔、有出错路径、有人要介入的环节；或第二层有两个以上模块。
- **不画**：没流程的（一个静态配置页、一张表）→ 改给界面草样，那是 vibe-flow §4 的原型；微任务 → 一律不画（缩放闸）。
- 用户说"别画了直接做"→ 立刻收。

## 共同规矩

- **框里写用户听得懂的词**：第一层写动作（"选日志文件""弹窗告诉你共几条"），不写"调用 parse()"。
- **我猜的一律标 `guess`**（黄色虚线）。确认一个就去掉 `guess`。
- **一张图约 15 个框封顶**（分层图按最小的格子数），超了拆成两张。
- **每个 `guess` 对应一条 `--q`**，问题写成用户能直接答的二选一 / 三选一。

## 流程图：写 `.d2`

只写框和线，**不写样式**（样式和配色在脚本里统一）：

```d2
direction: right
pick: 选日志文件 {class: step}
ok: 校验通过？ {class: ask}
bad: 记进错误清单 {class: step}
half: "半截帧\n丢掉 / 单独列？" {class: guess}
tell: 弹窗显示共几条 {class: done}
pick -> ok
ok -> bad: 否
bad -> tell
pick -> half: 解析不了 {class: maybe}
```

- `step` 已确认的步骤、`ask` 判断（菱形，出口边上写"是 / 否"或具体条件）、`guess` 我猜的、`done` 用户最后拿到的（绿）、`store` 文件 / 数据（圆柱）；猜的连线用 `maybe`。
- **出错路径必须画**——这是一句话需求里最常漏的东西。
- 多行标签用带 `\n` 的双引号字符串；带空格或标点的标签加引号更稳。

## 分层结构图：写 `.html` 片段

**只写结构，不写 `<html>` / `<style>` / `<script>`**（写了脚本会拒收），只用下面这套类名，样式由脚本统一加：

| 类名 | 用途 |
|---|---|
| `band` > `band-label` + `band-body` | 左侧竖排标签加括号，把几层框成一组（"应用""驱动与板级"） |
| `layer` > `name` | 一层，`name` 是层名；`layer narrow` 配 `style="--w:45%;--at:right"`（或 `center`）做错开的窄层 |
| `row`（`style="--cols:N"`） | N 等分的网格行；子元素加 `style="grid-column:span 2"` 可跨格 |
| `box c-色` > `h3` + `items` > `item` | 一组功能块；色：`c-blue` `c-teal` `c-violet` `c-rose` `c-peach` `c-orange` `c-gray` |
| `chips` > `chip` | 横排的小模块（外设、驱动）；`chip` 也能加 `c-色` |
| `gap` > `arrow`（`style="left:X%"`） | 两层之间的双向箭头 |
| 任意元素加 `guess` | 黄色虚线，表示我猜的 |

```html
<div class="band">
  <div class="band-label">应用</div>
  <div class="band-body">
    <section class="layer">
      <div class="name">APP 层</div>
      <div class="row" style="--cols:3">
        <div class="box c-rose"><h3>数据存储</h3><div class="items">
          <div class="item">事件存储</div><div class="item">参数存储</div></div></div>
        <div class="box c-peach"><h3>通信协议</h3><div class="items">
          <div class="item">IOT 远传协议</div><div class="item guess">光学接口协议？</div></div></div>
        <div class="box c-blue"><h3>计量方式</h3><div class="items">
          <div class="item">HALL 计量</div></div></div>
      </div>
    </section>
  </div>
</div>
<div class="gap"><div class="arrow" style="left:50%"></div></div>
<section class="layer">
  <div class="name">Driver 层</div>
  <div class="chips"><div class="chip">ADC</div><div class="chip">GPIO</div><div class="chip">串口</div></div>
</section>
```

颜色只用来**分组**（同一类功能一个色），别一格一个色；层与层之间用 `layer` 的灰框，不上色。

## 出页面

脚本在本 skill 的 `scripts/` 下，只用 stdlib；按后缀自动分流：

```bash
py -3 <clarify-needs 目录>/scripts/model_page.py docs/model/run.d2 \
  --title "<项目名>" --anchor "<真需求锚那一句>" --layer run \
  --q "<位置>::<要问的>" --q "..." --open
```

- `.d2` → 输出同名 `.html`；要本机有 `d2`。
- `.html` 片段 → 输出 `<名>.page.html`（不覆盖片段本身）；不需要 d2。
- 退出码：1 是 `.d2` 写错（报错行号就是 `.d2` 的行号）；2 是用法错——没装 d2、片段里带了 `<style>` 等、后缀不认识、输出会覆盖源文件。

然后：

1. **终端里只说一句**："图上有 N 处要你定，页面已经打开"，别在终端里把问题再列一遍。
2. 用户答完 → 改源文件（去掉 `guess`）→ 重新渲染 → 直到没有 `--q`，页面会显示"没有待定项"。

## 留底

- 文件放 `docs/model/`：第一层 `run.d2` → `run.html`；第二层 `build.d2` → `build.html`，或 `build.html` 片段 → `build.page.html`。
- `NEEDS.md` 的当前需求区放一行链接指向第一层的页面。
- 需求变了就覆盖更新，跟 NEEDS.md 一样不留废图。

## 降级

- **流程图但没装 d2**（脚本退出码 2）→ 在对话里画 ASCII 图，猜的地方标 `?`，末尾列要用户定的问题；不落 `docs/model/`。分层结构图不受影响。
- **终端看不到页面**（远程会话等）→ 同上。
