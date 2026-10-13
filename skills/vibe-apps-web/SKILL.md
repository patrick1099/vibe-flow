---
name: vibe-apps-web
description: Build or modify personal apps with a Web UI using Python, FastAPI and pywebview, or a browser/site delivery target. Load after vibe-flow and vibe-apps have selected the Web route, before scaffolding. Web 界面、浏览器访问、网站交付、FastAPI、pywebview；原生桌面走 vibe-apps-native。
---

# vibe-apps-web：Web 界面的默认 Python 实现

## 总纲

> 本页给 Web 路线的默认 Python 落法，业务规则与界面分离，通信走标准 HTTP。

先读 [vibe-apps](../vibe-apps/SKILL.md) 的路线优先级、共用边界和资源验证。已有项目或用户明确的语言/框架选择优先，本默认不触发自动迁移。用户已指定其他 Web 实现时沿用其项目规范，不把原生 Rust 参考套到 Web 上。

## 适用判定

| 特征 | 用哪个 |
|---|---|
| 独立 Python CLI，即使要分发 | **vibe-scripts** |
| 已选择 Web 界面 / 浏览器访问 / 网站交付 | **本 skill** |
| 原生桌面 / 上位机 / 低内存本地 GUI | **vibe-apps-native** |

**流程前置**：先由 `vibe-flow` 判档，再决定是否需要澄清或探方案。新建一个多模块的应用通常是好档（范围大），但好档不等于走满——目标清楚的小应用仍可直接落地；已有应用上的明确小改按省档走。判档、低耦合、文档、谁拍板都以 `vibe-flow`（§2、§4–§6）为准，本 skill 只给本栈的落法。

## 先确定 Web 交付方式

- **桌面 Web 壳**：本机服务与 pywebview 窗口，默认 PyInstaller 打包；本机文件对话框、`sys._MEIPASS` 与 EXE 验收只用于此方式。
- **浏览器/网站交付**：浏览器访问服务，部署后端与静态资源；不要求 pywebview、PyInstaller 或桌面窗口。文件按实际上传/下载契约处理，不在服务器弹文件选择框冒充访问者电脑选文件。
- 已有项目沿用实际交付方式；AGENTS 架构段的正文、脚手架与验收随实际方式裁剪，固定的只有共用标题。

## 本路线的默认技术栈

| 位置 | 选什么 |
|---|---|
| 逻辑 | 纯 Python |
| API | FastAPI + uvicorn |
| 前端 | 原生 HTML/JS + Tailwind 浏览器版（`@tailwindcss/browser@4.3.3`）+ DaisyUI（`daisyui@5.7.46`），**零构建、无 npm** |
| 窗口/入口 | 桌面壳用 pywebview（只当壳，通信走本地 HTTP，不用专有 JS 业务桥）；网站用浏览器入口 |
| 交付 | 桌面壳默认 PyInstaller；网站部署后端与静态资源 |
| 测试 | pytest |

**前端库本地化**：两份库文件下载到 `web/vendor/`（`tailwindcss-browser.js`、`daisyui.css`，需要多主题时加 `daisyui-themes.css`），页面只引本地路径、不引 CDN——自用工具常离线跑，走 CDN 断网就没样式。版本号钉死在上表，升级时改表、重新下载。Tailwind 官方把浏览器版定位为开发用途（页面加载时现编译样式）；自用工具接受这点换零构建，页面多到加载明显变慢再议。

**默认零构建**：应用的运行和打包都不用 npm，不上 React/Vue/npm 构建——打包简单，AI 改前端不用跑构建。（唯一用到 node 的是可选的 DESIGN.md 导出，见下文，只在改配色时跑一次。）用户明确选择的既有前端栈优先；包体积与运行内存是不同指标，有资源要求时按共用入口实测，不预先放弃资源目标。

## 桌面 Web 壳的默认五层（规则不知 UI 存在）

| 层 | 职责 | 性质 |
|---|---|---|
| `core/` | 全部业务逻辑 | 纯 Python，可 pytest，工具"真身" |
| `api/` | 把 core 暴露成 `/api/...` HTTP/JSON | 薄，只做 HTTP↔core 翻译 |
| `web/` | HTML/CSS/JS，`fetch('/api/..')` 调后端 | 只管展示，不含业务逻辑 |
| `app.py` | 后台起 uvicorn + 开 pywebview 窗口 | 只管拼装 |
| pywebview | 把 localhost 页面套成原生窗口 | 纯壳 |

桌面壳数据流：双击 exe → app.py 后台起 uvicorn(127.0.0.1:随机端口) → pywebview 加载该地址 → 前端 fetch → FastAPI 调应用操作 → JSON → 渲染。

网站保留 `core/`、`api/`、`web/` 的适用职责，入口改为服务部署，不创建 pywebview 窗口。应用操作先调用适配器取得数据，再将数据交纯规则；需要 IO 编排时由应用/组装层拥有，API 只翻译请求与结果，不把 IO 调用塞进 core。体量需要时才将编排拆成独立模块。

## 业务规则不依赖当前用户或窗口

数据显式传入，设备/存储 IO 由适配层处理；UI、连接、会话与任务状态由应用层拥有。逻辑分离降低换框架或交付方式的影响范围，实际可复用部分仍要核对依赖和行为契约。

```python
def summarize():                  # ❌ 读全局 DATA_FILE、焊死单用户
    data = load(DATA_FILE); ...
def summarize(data):              # ✅ 规则接收显式数据，不在规则里做 IO
    ...
```

**判据**：业务规则能直接构造输入调用，不依赖 GUI、全局当前用户或外部 IO；存储适配器由应用/组装层调用，取得的数据显式传给规则。保留这种边界即可，不提前建多用户/登录。

## core 里的变化轴（可插拔）

五层管的是上下分层；横向还有一类耦合五层管不到：**同一类会增删的成员**（数据源、导出格式、设备型号、第三方平台）。什么时候收口、什么时候要故障隔离，规矩在 `vibe-flow` §5「低耦合底线」及其 `references/low-coupling.md`，落到本栈：

- **放哪按成员碰不碰 IO 分**：纯规则类成员（格式转换、设备型号规则）放 `core/<轴>/`；碰网络、文件、设备、第三方平台的成员放 `adapters/<轴>/`，由应用/组装层调用，将取得的数据显式传给 core；core 不调用 IO 适配器。
- `<轴>/__init__.py` 放唯一的注册表；成员用属性自己声明能力。成员只是纯规则函数时一张 dict 就够。
- `api/` 和 `web/` 需要成员列表时，走一个 `/api/<轴>` 端点从注册表取，前端不写死名单。
- **成员各有外部依赖时**（第三方库、设备、网络），注册表只登记名字、惰性加载（写法见 `vibe-scripts` 的 `references/templates.md`）；列表类接口遇到单个成员加载或运行出错，只标它不可用，照常返回其余成员。用户点名操作这个成员，或操作要求全部成功时，明确报错，不假装成功。
- 只有一个成员时不建 `<轴>/` 目录，代码留在普通业务模块里聚成一处；第二个出现时再收成注册表。

## 远期：换零件、变网站

要换路线、框架、语言，或把应用变成多人网站时，读 [共用 evolution.md](../vibe-apps/references/evolution.md)。平时不用读；迁移前确认实际复用范围。

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

应用独占一个目录，按 `vibe-flow` §6 带 `AGENTS.md` ＋ `docs/BLUEPRINT.md` ＋ `docs/CHANGELOG.md`，有没做完的活时再加 `docs/HANDOFF.md`。这几份由收工时派出的 fork 按 `living-blueprint` 写（`vibe-flow` §8），实现者不写；例外只有两处：下面脚手架里 AGENTS.md 的架构约束段，和讨论中谈定时往 HANDOFF「已谈定」区记的条目（`vibe-flow` §4）。

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
├── app.py                 # 桌面壳：起 uvicorn + 开 pywebview；网站：服务组装入口
├── requirements.txt       # 按交付方式固定依赖；网站不用 pywebview/PyInstaller
└── build.spec             # 仅桌面壳：PyInstaller
```

**搭脚手架时，实现者把项目实际的架构约束写进 AGENTS.md，下面是桌面 Web 壳示例**：网站应删除壳与桌面打包约束，写实际服务入口、部署与文件传输契约；不能只改“实现选择”一行而保留 pywebview 五层。它是固定模板，也是文档闸认出 vibe-apps 项目的标记，所以随目录一起建，不等收工。AGENTS.md 其余几段和 BLUEPRINT、CHANGELOG 由收工时的 fork 补（骨架见 `living-blueprint` 的 `references/templates.md`）：
```markdown
## 架构约束（vibe-apps）
实现选择：Web 界面，Python + FastAPI + pywebview；交付 PyInstaller 桌面应用。
五层：core(纯逻辑可 pytest, 对"谁"无状态) / api(FastAPI 薄适配) / web(HTML+fetch) / app.py(拼装) / pywebview(壳)。
逻辑只放 core；api 只做 HTTP↔core 翻译；web 不含业务逻辑。
前端默认原生 HTML/JS + Tailwind 浏览器版 + DaisyUI，库文件放 web/vendor/ 本地引用，零构建无 npm；通信走 HTTP，不用 pywebview 专有桥。
有 DESIGN.md 时，颜色只改 DESIGN.md 再导出 web/theme.css，不手改 theme.css。
```
（这五层是 **默认 Python Web 实现结构**，属本 AGENTS.md。共用入口规定的可移植边界由 fork 写进蓝图；实际外部接口才记录协议契约，不把本分支的 HTTP、具名五层或专有桥限制强加给原生应用。网站交付时按实际职责重写模板正文，删除 pywebview/本地窗口及桌面打包约束。）

## 文件选择：按交付边界处理

**浏览器/网站交付**：使用浏览器选择文件、上传内容或下载输出，按项目契约定义格式、权限和传输目标。浏览器不能把访问者本地绝对路径交给服务端作本机路径使用；服务端只操作自己拥有的文件。服务端不调用 Tk/pywebview 文件选择框。

**桌面 Web 壳**（下述本机绝对路径方案仅适用于此方式）：

浏览器沙箱拿不到本地绝对路径，但业务又常需要。**统一做法**：在 `api/` 加一个 HTTP 端点（如 `/api/pick-path`），服务端调 pywebview 的 `create_file_dialog(FOLDER_DIALOG/...)` 弹原生框返回路径；开发态没有 webview 窗口时回退 `tkinter.filedialog`。前端仍只 `fetch` 这个端点。**不要**为此改用 pywebview 的 js_api 业务桥——那会让前端耦合壳、且没法用浏览器调。这是"通信一律走 HTTP"的唯一需要特殊处理点。

## 开发 / 交付两态

- **开发**：`uvicorn` 起服务，浏览器开 localhost，用 Chrome devtools 调 UI（pywebview 平时不参与，这正是不用专有桥的原因）。
- **桌面壳交付**：pywebview 套窗口 + PyInstaller 打 exe 发人。`web/` 由 FastAPI 的 `StaticFiles` 提供，`build.spec` 的 `datas` 必须收进整个 `web/`（含 `vendor/` 和 `theme.css`），打包后路径用 `sys._MEIPASS` 定位。**验收要断网跑打包出来的 exe**，样式完整才算过——源码能跑不代表 exe 没丢文件。
- **网站交付**：按实际部署入口启动后端与静态资源，从目标浏览器走通核心路径及上传/下载契约。若要求离线或本地部署，按该要求验证资源完整性；网站不要求 EXE、`sys._MEIPASS` 或桌面文件对话框。
