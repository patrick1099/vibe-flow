---
name: vibe-apps-web
description: Build or modify personal apps with a Web UI using Python, FastAPI and pywebview, or a browser/site delivery target. For direct user work, load after vibe-flow and vibe-apps select Web; assigned roles follow vibe-flow/references/role-reading.md. Web 界面、浏览器访问、网站交付、FastAPI、pywebview；原生桌面走 vibe-apps-native。
---

# vibe-apps-web：Web 界面的默认 Python 实现

## 总纲

> 本页给 Web 路线的默认 Python 落法，业务规则与界面分离，通信走标准 HTTP。

直接服务用户先读 [vibe-apps](../vibe-apps/SKILL.md) 的路线优先级、共用边界和资源验证；已分派角色按 [role-reading.md](../vibe-flow/references/role-reading.md) 只读适用公共部分，沿用已定路线/架构，不通读父入口。已有项目或用户明确的语言/框架选择优先，本默认不触发自动迁移。用户已指定其他 Web 实现时沿用其项目规范，不把原生 Rust 参考套到 Web 上。

## 适用判定

| 特征 | 用哪个 |
|---|---|
| 独立 Python CLI，即使要分发 | **vibe-scripts** |
| 已选择 Web 界面 / 浏览器访问 / 网站交付 | **本 skill** |
| 原生桌面 / 上位机 / 低内存本地 GUI | **vibe-apps-native** |

**流程前置**：直接服务用户先由 `vibe-flow` 判档，已分派角色沿用派工档位；再决定是否需要澄清或探方案。新建一个多模块的应用通常是好档（范围大），但好档不等于走满——目标清楚的小应用仍可直接落地；已有应用上的明确小改按省档走。判档、低耦合、文档、谁拍板都以 `vibe-flow`（§2、§4–§6）为准，本 skill 只给本栈的落法。

## 先确定 Web 交付方式

- **桌面 Web 壳**：本机服务与 pywebview 窗口，默认 PyInstaller 打包；本机文件对话框、`sys._MEIPASS` 与 EXE 验收只用于此方式。关窗后不需要继续工作时，服务和窗口同进程，关窗整体退出；需要继续工作时，按 [vibe-apps「关窗即释放界面进程」](../vibe-apps/SKILL.md#架构讨论与共用边界) 把服务作为内核进程单独运行，pywebview 窗口单独一个进程，关窗时窗口进程及其 WebView2 子进程全部退出（本机样例 WebView2 一组约 450–550 MiB）。
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
| 测试 | 后端 pytest；需要前端无 DOM 行为测试时用 Node 内置 `node --test`（仅开发依赖） |

**前端库本地化**：两份库文件下载到 `web/vendor/`（`tailwindcss-browser.js`、`daisyui.css`，需要多主题时加 `daisyui-themes.css`），页面只引本地路径、不引 CDN——自用工具常离线跑，走 CDN 断网就没样式。版本号钉死在上表，升级时改表、重新下载。Tailwind 官方把浏览器版定位为开发用途（页面加载时现编译样式）；自用工具接受这点换零构建，页面多到加载明显变慢再议。

**默认零构建**：应用的运行和打包都不用 npm，不上 React/Vue/npm 构建——打包简单，AI 改前端不用跑构建。DESIGN.md 导出和前端测试可以使用 Node 开发工具；开发检查依赖与应用运行/打包依赖分开，按项目实际记录。用户明确选择的既有前端栈优先；包体积与运行内存是不同指标，有资源要求时按共用入口实测，不预先放弃资源目标。

## 选定 Clean 分层时的 Web 映射

先完成共用入口的架构讨论。以下层次、脚手架和模板是选定 Clean 分层后的实现示例，前端展示层按共用入口的单向数据流规则；采用其他已定结构时按职责裁剪，不能把模板当成选型结论。

| 层 | 职责 | 性质 |
|---|---|---|
| `core/` | domain：业务规则与领域数据 | 纯 Python |
| `application/` | 用例、会话/任务、ports | 依赖 domain，不导入 FastAPI/具体 IO |
| `adapters/` | 实现 ports：设备、存储等 | 依赖内层契约 |
| `api/` | HTTP 请求/响应与用例转换 | 入站适配器，不做业务编排 |
| `web/view.js` | DOM 事件处理与 render | View，经 client 提交意图，不写业务判断 |
| `web/state.mjs` | 按需：跨事件的展示状态与 apply | 满足抽取条件才建；不依赖 DOM/fetch，可 `node --test` |
| `web/client.js` | 实现前端请求接口，fetch/JSON | HTTP 适配器，不决定业务规则 |
| `app.py` | 后台起 uvicorn + 开 pywebview 窗口 | 只管拼装 |
| pywebview | 把 localhost 页面套成原生窗口 | 纯壳 |

桌面壳数据流：app.py 起本地服务与窗口 → DOM 事件 → 注入的 HTTP client → FastAPI → application 用例 → domain / 注入的 IO port → 响应经 apply 进展示状态（简单页面直接交给 render）→ render 更新 DOM。浏览器与服务器是两个运行边界，不共用可变状态，也不让后端依赖前端模块。

网站沿用相同职责，入口改为服务部署，不创建 pywebview 窗口。application 用例通过自身定义的 ports 编排 IO，把数据交 domain；入口注入实现，API 不承担工作流。纯静态展示不造空状态模块；已有前端框架用它自己的绑定机制实现这些边界，不强制新增运行框架。

## 业务规则不依赖当前用户或窗口

数据显式传入，设备/存储 IO 由适配层处理；连接、会话与任务状态由 application 拥有，前端跨事件的展示状态归展示层（按需的 `state.mjs`）；简单的局部草稿留在 DOM 由 View 持有，参与联动、异步预演或多步流程的草稿归展示状态。服务端业务校验是权威，前端可做输入格式与交互校验，不复制业务决策。逻辑分离降低换框架或交付方式的影响范围，实际可复用部分仍要核对依赖和行为契约。

```python
def summarize():                  # ❌ 读全局 DATA_FILE、焊死单用户
    data = load(DATA_FILE); ...
def summarize(data):              # ✅ 规则接收显式数据，不在规则里做 IO
    ...
```

**判据**：业务规则能直接构造输入调用，不依赖 GUI、全局当前用户或外部 IO；application 只通过内层 port 使用存储，入口注入具体适配器，取得的数据显式传给规则。保留这种边界即可，不提前建多用户/登录。

## core 里的变化轴（可插拔）

选定 Clean 分层时，它管依赖方向；横向还有一类成员选择：**同一类会增删的成员**（数据源、导出格式、设备型号、第三方平台）。什么时候收口、什么时候要故障隔离，规矩在 `vibe-flow` §5「低耦合底线」及其 `references/low-coupling.md`，落到本栈：

- **放哪按成员碰不碰 IO 分**：纯规则类成员（格式转换、设备型号规则）放 `core/<轴>/`；碰网络、文件、设备、第三方平台的成员放 `adapters/<轴>/`，由入口注入 application 定义的 port，将取得的数据显式传给 core；core 不调用 IO 适配器。
- `<轴>/__init__.py` 放唯一的注册表；成员用属性自己声明能力。成员只是纯规则函数时一张 dict 就够。
- `api/` 和 `web/` 需要成员列表时，走 `/api/<轴>` → application 的成员查询用例。纯规则名单可来自 core 注册表；IO 名单经入口注入的 catalog port 读取外层注册表，API/用例不直接导入 adapters，前端不写死名单。
- **成员各有外部依赖时**（第三方库、设备、网络），注册表只登记名字、惰性加载（写法见 `vibe-scripts` 的 `references/templates.md`）；列表类接口遇到单个成员加载或运行出错，只标它不可用，照常返回其余成员。用户点名操作这个成员，或操作要求全部成功时，明确报错，不假装成功。
- 只有一个成员时不建 `<轴>/` 目录：纯规则聚在 core 普通模块，IO 聚在 adapters 普通模块；第二个出现时再收成注册表。

## 远期：换零件、变网站

要换路线、框架、语言，或把应用变成多人网站时，读 [共用 evolution.md](../vibe-apps/references/evolution.md)。平时不用读；迁移前确认实际复用范围。

## 界面规范与效果图

DESIGN.md、效果图先行与截图对照按 [vibe-apps「界面：效果图先行」](../vibe-apps/SKILL.md#界面效果图先行) 走。Web 路线的效果图直接写在 `web/`，可以用 DaisyUI 组件，定稿后就是前端起点，不另画一份；接入真实数据、放进 pywebview 后仍按该节对照一次。本栈落法：

- 用共用入口的导出命令把 DESIGN.md 导成 `web/theme.css`（目标路径换成 `web/theme.css.tmp`），不手写第二份色值。
- 页面在 `daisyui.css` **之后** `<link>` 引 `theme.css`，默认主题下按钮、`bg-primary` 这类工具类就都跟着变。用 `data-theme` 切到别的 DaisyUI 主题时，theme.css 管不到那些主题。
- **只有颜色会自动生效**。圆角、间距导出后变量名和 DaisyUI 对不上，靠 DESIGN.md 正文描述 + DaisyUI 默认值；css-vars 不导出字体，字体在 `web/` 的样式里按 DESIGN.md 写一处。

## 设计记录（意图驱动）

应用独占一个目录，按 `vibe-flow` §6 带 `AGENTS.md` ＋ `docs/BLUEPRINT.md` ＋ `docs/CHANGELOG.md`，有没做完的活时再加 `docs/HANDOFF.md`。这几份由收工时派出的 fork 按 `living-blueprint` 写（`vibe-flow` §8），实现者不写；例外只有两处：下面脚手架里 AGENTS.md 的架构约束段，和讨论中谈定时往 HANDOFF「已谈定」区记的条目（`vibe-flow` §4）。

## 脚手架（选定 Clean 分层后按需建目录）

```
mytool/
├── AGENTS.md              # 交接入口：先读顺序/命令/坑/搜不出来的约定 + 下方架构约束段
├── docs/BLUEPRINT.md      # 当前功能全貌（living-blueprint）
├── docs/CHANGELOG.md      # 为什么变更，只追加（living-blueprint）
├── docs/HANDOFF.md        # 可选：只在有没做完的活时存在，做完删掉（living-blueprint）
├── core/*.py              # domain：纯业务规则
├── application/           # 用例、会话/任务及 ports
├── adapters/              # 实际 IO 的 port 实现
├── core/<轴>/ 或 adapters/<轴>/   # 可选：某条轴出现第二个成员时才建（纯规则进 core，碰 IO 进 adapters）
├── api/server.py          # FastAPI 薄适配
├── web/index.html         # View 的页面布局
├── web/view.js            # DOM 事件处理与 render
├── web/state.mjs          # 按需：跨事件展示状态 + apply；可无 DOM 测试
├── web/client.js          # 注入的 HTTP client 实现
├── web/app.js             # 前端组装入口
├── web/vendor/            # tailwindcss-browser.js、daisyui.css（本地副本，版本见技术栈表）
├── web/theme.css          # 由 DESIGN.md 导出，不手改
├── DESIGN.md              # 界面规范（见 vibe-apps「界面：效果图先行」）
├── tests/                # domain/用例/展示状态转换行为与禁止导入检查
├── app.py                 # 桌面壳：起 uvicorn + 开 pywebview；网站：服务组装入口
├── requirements.txt       # 按交付方式固定依赖；网站不用 pywebview/PyInstaller
└── build.spec             # 仅桌面壳：PyInstaller
```

**搭脚手架时，实现者把项目实际的架构约束写进 AGENTS.md，下面是桌面 Web 壳示例**：网站应删除壳与桌面打包约束，写实际服务入口、部署与文件传输契约；不能只改“实现选择”一行而保留桌面壳职责。固定的是下方标题，它是文档闸认出 vibe-apps 项目的标记；正文须按架构讨论的实际选择填写，所以随目录一起建，不等收工。AGENTS.md 其余几段和 BLUEPRINT、CHANGELOG 由收工时的 fork 补（骨架见 `living-blueprint` 的 `references/templates.md`）：
```markdown
## 架构约束（vibe-apps）
实现选择：Web 界面，Python + FastAPI + pywebview；交付 PyInstaller 桌面应用。
架构：Clean 分层；core 为 domain，application 定义用例/ports，adapters 实现 IO，api 只做 HTTP↔用例转换。
前端单向数据流：DOM 事件经注入的 client 请求后端，render 写 DOM；命中抽取条件的跨事件状态才建 web/state.mjs（状态 + apply，不依赖 DOM/fetch），否则结果直接交 render；业务判断不写在事件处理里。内层不导入外层实现，入口负责组装。
在此写明已选架构的验证方式；有自动检查时列实际命令及覆盖范围，越界非零退出，未自动覆盖的边界如实记录。
前端默认原生 HTML/JS + Tailwind 浏览器版 + DaisyUI，库文件放 web/vendor/ 本地引用，零构建无 npm；通信走 HTTP，不用 pywebview 专有桥。
有 DESIGN.md 时，颜色只改 DESIGN.md 再导出 web/theme.css，不手改 theme.css。
```
（这些模块名是 **默认 Python Web 实现结构**，属本 AGENTS.md。共用入口规定的可移植边界由 fork 写进蓝图；实际外部接口才记录协议契约，不把本分支的 HTTP 或专有桥限制强加给原生应用。网站交付时按实际职责重写模板正文，删除 pywebview/本地窗口及桌面打包约束。）

## 文件选择：按交付边界处理

**浏览器/网站交付**：使用浏览器选择文件、上传内容或下载输出，按项目契约定义格式、权限和传输目标。浏览器不能把访问者本地绝对路径交给服务端作本机路径使用；服务端只操作自己拥有的文件。服务端不调用 Tk/pywebview 文件选择框。

**桌面 Web 壳**（下述本机绝对路径方案仅适用于此方式）：

浏览器沙箱拿不到本地绝对路径，但业务又常需要。**统一做法**：在 `api/` 加一个 HTTP 端点（如 `/api/pick-path`），端点调用 application 的路径选择用例，用例通过自身定义的 picker port 请求文件选择能力，由桌面适配器在 GUI 允许的线程调 `create_file_dialog(FOLDER_DIALOG/...)`，开发态使用显式选择的 Tk 适配器。前端由 client 请求该端点并接收结果；窗口句柄和框架调用不进入展示状态或用例层。**不要**为此改用 pywebview 的 js_api 业务桥——那会让前端耦合壳、且没法用浏览器调。这是"通信一律走 HTTP"的唯一需要特殊处理点。

服务与窗口拆成两个进程时，服务是内核，不能弹框，也不能为此自建 Tk 窗口：picker 适配器放在窗口进程，选中的路径作为普通请求参数交给内核；具体由窗口进程怎么接住前端的选择请求，按项目谈定。窗口没开就没有选择能力，依赖它的操作明确报错或取消。

## 前端边界怎么验证

按共用 [验证要求](../vibe-apps/references/clean-mvvm.md#验证要求) 和本次规模选择检查，不把“零构建”解释成不能有开发测试。前端抽出了跨事件状态时，把它写成 ES module（例如 `state.mjs`，并同步入口引用）；测试通过 `node --test tests/frontend/*.test.mjs` 导入生产模块，以假 client 驱动事件序列：失败、乱序与晚到响应。已有模块方案沿用（含旧项目的 `viewmodel.mjs`），不为测试重写一份状态。

测试夹具可把 `fetch`、`XMLHttpRequest`、`document`、`window`、`localStorage` 替换为一经访问即报错的对象，运行后恢复；测试的是本次执行到的路径，不能据此宣称完整源码没有越界。前端依赖检查同样默认轻量，按共用验证要求的升级条件再加强；需要静态检查时选择支持实际 JS 模块语法的工具，开发依赖单独记录。不能用后端 pytest 通过或几个关键词搜索代替前端验证。

## 开发 / 交付两态

- **开发**：`uvicorn` 起服务，浏览器开 localhost，用 Chrome devtools 调 UI（pywebview 平时不参与，这正是不用专有桥的原因）。
- **桌面壳交付**：pywebview 套窗口 + PyInstaller 打 exe 发人。`web/` 由 FastAPI 的 `StaticFiles` 提供，`build.spec` 的 `datas` 必须收进整个 `web/`（含 `vendor/` 和 `theme.css`），打包后路径用 `sys._MEIPASS` 定位。**验收要断网跑打包出来的 exe**，样式完整才算过——源码能跑不代表 exe 没丢文件。
- **网站交付**：按实际部署入口启动后端与静态资源，从目标浏览器走通核心路径及上传/下载契约。若要求离线或本地部署，按该要求验证资源完整性；网站不要求 EXE、`sys._MEIPASS` 或桌面文件对话框。
