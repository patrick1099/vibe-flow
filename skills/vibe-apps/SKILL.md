---
name: vibe-apps
description: Use when building a personal Python tool/app that has a UI, will be packaged and shared with others (exe), or might later grow into a website — 带界面的小工具、桌面工具、要发给别人的应用、可能变网站的 Python 应用；GUI、界面、打包 exe、pywebview、FastAPI。Load BEFORE scaffolding. For one-shot CLI / single-file scripts use vibe-scripts instead.
---

# vibe-apps：带界面 / 要分发的 Python 应用架构

## 总纲

> 一套栈通吃自用与分发，逻辑与界面物理隔离，核心对"谁"无状态。

省 token 原理：单栈免重构；core 纯逻辑既能 pytest，又为将来多用户/网站留门；HTTP 边界强制低耦合，AI 改一处只读一层。

## 适用判定（先分清 vs vibe-scripts）

| 特征 | 用哪个 |
|---|---|
| 跑完即弃 / 命令行 / 单文件 | **vibe-scripts** |
| 有界面 / 要发给别人(exe) / 要长期活或可能变网站 | **本 skill** |

**流程前置**：先由 `vibe-flow` 判档，再决定是否需要澄清或探方案。新建一个多模块的应用通常是好档（范围大），但好档不等于走满——目标清楚的小应用仍可直接落地；已有应用上的明确小改按省档走。判档、低耦合、文档、谁拍板都以 `vibe-flow`（§2、§4–§6）为准，本 skill 只给本栈的落法。

## 技术栈（定死，不再选）

| 位置 | 选什么 |
|---|---|
| 逻辑 | 纯 Python |
| API | FastAPI + uvicorn |
| 前端 | 原生 HTML/JS + Tailwind 浏览器版（`@tailwindcss/browser@4.3.3`）+ DaisyUI（`daisyui@5.7.46`），**零构建、无 npm** |
| 窗口 | pywebview（只当壳；通信走本地 HTTP，**不用其专有 JS 桥**）|
| 打包 | PyInstaller |
| 测试 | pytest |

**前端库本地化**：两份库文件下载到 `web/vendor/`（`tailwindcss-browser.js`、`daisyui.css`，需要多主题时加 `daisyui-themes.css`），页面只引本地路径、不引 CDN——自用工具常离线跑，走 CDN 断网就没样式。版本号钉死在上表，升级时改表、重新下载。Tailwind 官方把浏览器版定位为开发用途（页面加载时现编译样式）；自用工具接受这点换零构建，页面多到加载明显变慢再议。

**默认零构建**：应用的运行和打包都不用 npm，不上 React/Vue/npm 构建——打包简单，AI 改前端不用跑构建。（唯一用到 node 的是可选的 DESIGN.md 导出，见下文，只在改配色时跑一次。）小体积是审美需求、已主动放弃（Python 打包 30~40MB 无所谓）。

## 五层（依赖方向固定 App→Core, Core 不知 UI 存在）

| 层 | 职责 | 性质 |
|---|---|---|
| `core/` | 全部业务逻辑 | 纯 Python，可 pytest，工具"真身" |
| `api/` | 把 core 暴露成 `/api/...` HTTP/JSON | 薄，只做 HTTP↔core 翻译 |
| `web/` | HTML/CSS/JS，`fetch('/api/..')` 调后端 | 只管展示，不含业务逻辑 |
| `app.py` | 后台起 uvicorn + 开 pywebview 窗口 | 只管拼装 |
| pywebview | 把 localhost 页面套成原生窗口 | 纯壳 |

数据流：双击 exe → app.py 后台起 uvicorn(127.0.0.1:随机端口) → pywebview 加载该地址 → 前端 fetch → FastAPI 调 core → JSON → 渲染。

## 头号铁律：core 对"谁"无状态（唯一将来难补的门）

框架里别的都便宜可换，唯独这条焊死了，将来变网站就得回头**重写 core**。

```python
def summarize():                  # ❌ 读全局 DATA_FILE、焊死单用户
    data = load(DATA_FILE); ...
def summarize(data, store):       # ✅ 数据/存储显式传入
    ...
```

**判据**：core 里任何函数都能在 pytest 里直接构造输入调用、不碰全局——能做到，门就开着。这跟"core 要可 pytest"是同一件事，不额外花钱，也正是 vibe-scripts「Core 纯函数不 IO」纪律的放大版。**分寸**：只是别把单用户假设焊进 core，不是现在就建多用户/登录（YAGNI）。

## core 里的变化轴（可插拔）

五层管的是上下分层；横向还有一类耦合五层管不到：**同一类会增删的成员**（数据源、导出格式、设备型号、第三方平台）。什么时候收口、什么时候要故障隔离，规矩在 `vibe-flow` §5「低耦合底线」，落到本栈：

- **放哪按成员碰不碰 IO 分**：纯规则类成员（格式转换、设备型号规则）放 `core/<轴>/`；碰网络、文件、设备、第三方平台的成员放 `adapters/<轴>/`，通过参数注入 core——core 不碰 IO 这条不因为可插拔而破例。
- `<轴>/__init__.py` 放唯一的注册表；成员用属性自己声明能力。成员只是纯规则函数时一张 dict 就够。
- `api/` 和 `web/` 需要成员列表时，走一个 `/api/<轴>` 端点从注册表取，前端不写死名单。
- **成员各有外部依赖时**（第三方库、设备、网络），注册表只登记名字、惰性加载（写法见 `vibe-scripts` 的 `references/templates.md`）；列表类接口遇到单个成员加载或运行出错，只标它不可用，照常返回其余成员。用户点名操作这个成员，或操作要求全部成功时，明确报错，不假装成功。
- 只有一个成员时不建 `<轴>/` 目录，代码留在普通业务模块里聚成一处；第二个出现时再收成注册表。

## 远期：换零件、变网站

要换框架，或把应用变成多人网站时，读 `references/evolution.md`。平时不用读——只要守住上面的头号铁律，这些将来都便宜。

## 界面规范（DESIGN.md，可选）

**何时建**：界面超过一个页面，或要交给别的 AI 改界面时；单页小工具不建，DaisyUI 默认主题就够。

- 放项目根 `DESIGN.md`（沿用上游约定，别的 agent 能自己找到）。**格式以本 skill 的 `vendor/design-md/spec.md` 为准**——那是上游原文，这里不复述。上游更新时跑 `py -3 <本 skill 目录>/scripts/sync_upstream.py`（在哪个目录跑都行；`--check` 只看有没有更新、不写文件），规范和 CLI 版本一起刷新，本文不用改。
- **颜色 token 用 DaisyUI 的变量名**：`primary` `secondary` `accent` `neutral` `base-100` `base-200` `base-300` `base-content` `info` `success` `warning` `error`，以及各自的 `*-content`（放在该色上的文字色）。
- **颜色只写在 DESIGN.md 一处**，`web/theme.css` 由它生成，不手写第二份色值。`<ver>` 取 `vendor/design-md/cli-package.json` 里的 `version`，让 CLI 和存着的规范是同一版：
  ```
  npx -y -p @google/design.md@<ver> designmd lint DESIGN.md && npx -y -p @google/design.md@<ver> designmd export DESIGN.md --format css-vars > web/theme.css.tmp
  ```
  **必须用 `&&` 串成一条**：DESIGN.md 有错时 lint 退出非零，而 export 照样退出 0、会导出坏结果。整条成功后再把 `theme.css.tmp` 改名覆盖 `theme.css`；失败就修 DESIGN.md，旧 theme.css 不动。Windows 上命令名必须用 `designmd`。
- 页面在 `daisyui.css` **之后** `<link>` 引 `theme.css`，默认主题下按钮、`bg-primary` 这类工具类就都跟着变。用 `data-theme` 切到别的 DaisyUI 主题时，theme.css 管不到那些主题。
- **只有颜色会自动生效**。圆角、间距导出后变量名和 DaisyUI 对不上，靠 DESIGN.md 正文描述 + DaisyUI 默认值。
- 风格起点可以从 [awesome-design-md](https://github.com/voltagent/awesome-design-md) 挑一份拷过来改，颜色名改成上面那套。

## 设计记录（意图驱动）

应用独占一个目录，按 `vibe-flow` §6 带 `AGENTS.md` ＋ `docs/BLUEPRINT.md` ＋ `docs/CHANGELOG.md`，有没做完的活时再加 `docs/HANDOFF.md`。这几份由收工时派出的 fork 按 `living-blueprint` 写（`vibe-flow` §8），实现者不写；唯一例外是下面脚手架里 AGENTS.md 的架构约束段。

## 脚手架（建目录）

```
mytool/
├── AGENTS.md              # 交接入口：先读顺序/命令/坑/搜不出来的约定 + 下方架构约束段
├── docs/BLUEPRINT.md      # 当前功能全貌（living-blueprint）
├── docs/CHANGELOG.md      # 为什么变更，只追加（living-blueprint）
├── docs/HANDOFF.md        # 可选：只在有没做完的活时存在，做完删掉（living-blueprint）
├── core/*.py              # 纯逻辑, 可 pytest, 对"谁"无状态
├── core/<轴>/ 或 adapters/<轴>/   # 可选：某条轴出现第二个成员时才建（纯规则进 core，碰 IO 进 adapters）
├── api/server.py          # FastAPI 薄适配
├── web/{index.html,app.js}   # fetch 调 api; Tailwind 工具类 + DaisyUI 组件
├── web/vendor/            # tailwindcss-browser.js、daisyui.css（本地副本，版本见技术栈表）
├── web/theme.css          # 可选：由 DESIGN.md 导出，不手改
├── DESIGN.md              # 可选：界面规范（见「界面规范」节）
├── tests/test_*.py        # pytest 测 core
├── app.py                 # 起 uvicorn + 开 pywebview
├── requirements.txt       # fastapi uvicorn pywebview (+pyinstaller)
└── build.spec             # PyInstaller
```

**搭脚手架时，实现者把下面这段 vibe-apps 架构约束写进 AGENTS.md**：它是固定模板，也是文档闸认出 vibe-apps 项目的标记，所以随目录一起建，不等收工。AGENTS.md 其余几段和 BLUEPRINT、CHANGELOG 由收工时的 fork 补（骨架见 `living-blueprint` 的 `references/templates.md`）：
```markdown
## 架构约束（vibe-apps）
五层：core(纯逻辑可 pytest, 对"谁"无状态) / api(FastAPI 薄适配) / web(HTML+fetch) / app.py(拼装) / pywebview(壳)。
逻辑只放 core；api 只做 HTTP↔core 翻译；web 不含业务逻辑。
前端默认原生 HTML/JS + Tailwind 浏览器版 + DaisyUI，库文件放 web/vendor/ 本地引用，零构建无 npm；通信走 HTTP，不用 pywebview 专有桥。
有 DESIGN.md 时，颜色只改 DESIGN.md 再导出 web/theme.css，不手改 theme.css。
```
（这五层是 **Python 特定实现结构**，属本 AGENTS.md。其中**换语言仍成立的原则**——逻辑与 UI/框架解耦、逻辑层可独立测试、通信走标准协议不用专有桥——由 fork 另写进 `BLUEPRINT.md` 第 4 节「硬约束·可移植架构约束」，见 `living-blueprint`；蓝图不收具名五层。）

## 原生文件/目录选择（webview 里拿不到本地绝对路径）

浏览器沙箱拿不到本地绝对路径，但业务又常需要。**统一做法**：在 `api/` 加一个 HTTP 端点（如 `/api/pick-path`），服务端调 pywebview 的 `create_file_dialog(FOLDER_DIALOG/...)` 弹原生框返回路径；开发态没有 webview 窗口时回退 `tkinter.filedialog`。前端仍只 `fetch` 这个端点。**不要**为此改用 pywebview 的 js_api 业务桥——那会让前端耦合壳、且没法用浏览器调。这是"通信一律走 HTTP"的唯一需要特殊处理点。

## 开发 / 交付两态

- **开发**：`uvicorn` 起服务，浏览器开 localhost，用 Chrome devtools 调 UI（pywebview 平时不参与，这正是不用专有桥的原因）。
- **交付**：pywebview 套窗口 + PyInstaller 打 exe 发人。`web/` 由 FastAPI 的 `StaticFiles` 提供，`build.spec` 的 `datas` 必须收进整个 `web/`（含 `vendor/` 和 `theme.css`），打包后路径用 `sys._MEIPASS` 定位。**验收要断网跑打包出来的 exe**，样式完整才算过——源码能跑不代表 exe 没丢文件。
