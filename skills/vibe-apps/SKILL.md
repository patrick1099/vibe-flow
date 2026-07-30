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

**流程前置**：先由 `vibe-flow` 判档，再决定是否需要澄清或探方案。带界面 / 要分发的应用基本都落**好档**，但好档不等于走满——目标清楚的小应用仍可直接落地；只有严重歧义、用户明确要求或高风险设计才展开完整的方案对比。

## 技术栈（定死，不再选）

| 位置 | 选什么 |
|---|---|
| 逻辑 | 纯 Python |
| API | FastAPI + uvicorn |
| 前端 | 原生 HTML/CSS/JS + CDN 引 CSS 框架(如 Pico.css)，**零构建、无 npm** |
| 窗口 | pywebview（只当壳；通信走本地 HTTP，**不用其专有 JS 桥**）|
| 打包 | PyInstaller |
| 测试 | pytest |

**禁止**：Tauri / Rust / Electron；默认不上 React/Vue/node 构建。小体积是审美需求、已主动放弃（Python 打包 30~40MB 无所谓）。

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

## 换零件规则

- **同语言换零件**（FastAPI↔Django、pywebview↔别的窗口库、原生 HTML↔React）= 便宜，core 和 web 不动。
- **换到 Rust/Tauri ≠ 推倒重来**：只要 core 守住"无状态、模块化"，就能用 PyO3 **按模块**把逻辑换成 Rust（Python API 不变、import 姿势照旧）；耐用件（协议编解码、校验、核心算法）甚至可一开始就用 Rust 写、两轨共享。真到分发/毕业 Tauri 是**逐模块迁移**，不是整个重写。迁移时机、双轨方案、分发三档见 docs `vibe-apps-栈权衡与改进候选.md` §8。
- 判据：换语言不必然贵——**前提是 core 一直保持可 PyO3 化**（这跟"core 对谁无状态"是同一条纪律的白捡收益）。

## 成长为多人网站

同一 `core+api+web`，只换**交付层**：部署 FastAPI 到服务器（丢掉 pywebview/PyInstaller）、`api/` 加登录鉴权、加数据库按用户隔离。`core/` 不动——**前提是它从一开始就对"谁"无状态**。多人+登录+后台恰是 Django 甜区，也是 FastAPI→Django 便宜 swap 兑现之时。别提前建登录（YAGNI）。

## 设计记录（意图驱动）

按 `vibe-flow` §6 的规则留文档：单会话小应用不强制建文档；跨会话且需求仍在演化时用 `docs/NEEDS.md`；长期维护、以后会按意图重构时，用 `living-blueprint` 建并维护 `docs/BLUEPRINT.md`。

## 脚手架（建目录）

```
mytool/
├── CLAUDE.md              # 下方 vibe-apps 架构约束段
├── docs/BLUEPRINT.md      # 长期维护时由 living-blueprint 建；小应用可无
├── core/*.py              # 纯逻辑, 可 pytest, 对"谁"无状态
├── api/server.py          # FastAPI 薄适配
├── web/{index.html,app.js,style.css}   # fetch 调 api; CDN 引 Pico.css
├── tests/test_*.py        # pytest 测 core
├── app.py                 # 起 uvicorn + 开 pywebview
├── requirements.txt       # fastapi uvicorn pywebview (+pyinstaller)
└── build.spec             # PyInstaller
```

**CLAUDE.md 追加 vibe-apps 架构约束段**：
```markdown
## 架构约束（vibe-apps）
五层：core(纯逻辑可 pytest, 对"谁"无状态) / api(FastAPI 薄适配) / web(HTML+fetch) / app.py(拼装) / pywebview(壳)。
逻辑只放 core；api 只做 HTTP↔core 翻译；web 不含业务逻辑。
前端默认原生 HTML/CSS/JS + CDN CSS，零构建无 npm；通信走 HTTP，不用 pywebview 专有桥。
```
（这五层是 **Python 特定实现结构**，属本 CLAUDE.md。其中**换语言仍成立的原则**——逻辑与 UI/框架解耦、逻辑层可独立测试、通信走标准协议不用专有桥——另写进 `BLUEPRINT.md` 第 4 节「硬约束·可移植架构约束」，见 `living-blueprint`；蓝图不收具名五层。）

## 原生文件/目录选择（webview 里拿不到本地绝对路径）

浏览器沙箱拿不到本地绝对路径，但业务又常需要。**统一做法**：在 `api/` 加一个 HTTP 端点（如 `/api/pick-path`），服务端调 pywebview 的 `create_file_dialog(FOLDER_DIALOG/...)` 弹原生框返回路径；开发态没有 webview 窗口时回退 `tkinter.filedialog`。前端仍只 `fetch` 这个端点。**不要**为此改用 pywebview 的 js_api 业务桥——那会让前端耦合壳、且没法用浏览器调。这是"通信一律走 HTTP"的唯一需要特殊处理点。

## 开发 / 交付两态

- **开发**：`uvicorn` 起服务，浏览器开 localhost，用 Chrome devtools 调 UI（pywebview 平时不参与，这正是不用专有桥的原因）。
- **交付**：pywebview 套窗口 + PyInstaller 打 exe 发人。

## 反模式（出现即返工）

- 业务逻辑写进 api/ 或 web/（必须只在 core/）
- core 读全局 / 写死数据文件 / 假设单用户
- 用 pywebview 专有 JS 桥（不可移植、没法浏览器调）
- 为了小体积去上 Tauri/Rust（小体积是审美，已放弃）
- 默认就上 React/Vue + node 构建
- 长期维护项目没有可供后续会话读取的当前需求/蓝图
