# 原生 Python：ttkbootstrap 默认实现

只在原生分支实际采用 Python 时读。ttkbootstrap 是新建、未指定 GUI 的本地工具默认；已有 Qt、Dear PyGui、Tk 或其他框架不因这份参考自动迁移。

## 选定 Clean 分层时的结构示例

新项目先完成架构讨论。以下骨架仅供选定 Clean 分层时使用；简单项目按已定结构裁剪，不为套模板创建空模块。

```text
mytool/
├── AGENTS.md
├── DESIGN.md           界面规范（见 vibe-apps「界面：效果图先行」）
├── docs/{BLUEPRINT.md,CHANGELOG.md}
├── docs/mockup/        定稿的 HTML 效果图
├── app.py              入口、配置与资源组装
├── core.py             domain：纯业务规则与领域数据
├── application.py      用例、任务生命周期与外部依赖 ports
├── state.py            按需：满足展示状态抽取条件才建，状态 + apply 纯函数
├── ui.py               View：ttkbootstrap 控件、Tk Variable 与回调
├── design_tokens.py    由 DESIGN.md 生成（design_theme.py），不手改
├── theme.py            用 design_tokens 建项目主题、配命名字体与控件 Style
├── adapters.py         按需：串口、文件、存储等 IO
├── tests/              针对性业务与错误路径测试
└── requirements.txt    固定实际依赖
```

目录与模块按实际体量调整，职责遵守 [应用分层与展示状态](../../vibe-apps/references/clean-mvvm.md)。有会话/任务编排就放 application，不留在 ui.py 等复杂了再拆。实际 IO 的窄 port 可用 Protocol 或注入 callable，定义在使用方内层，即使只有一个实现也隔离；没有业务规则时不造空 domain，没有 IO 时不造空 port。

## 实现要点

- 有效果图时照图搭布局（见下节）；业务校验留在 core，按钮回调取输入后调用例，不写业务判断。简单字段用 Tk Variable（`textvariable`）承担控件同步，提交时读取，不再复制进另一份状态对象；`state.py` 只放影响界面判断的状态和 apply，要能不开窗口测试。主题与字体由 UI 组装处统一设置，不把样式散进业务逻辑。
- Tk 控件只在主线程操作。需要后台 IO 时，线程将结果放入事件通道，主线程用有节制的 `after()` 消费事件（有 `state.py` 时经 apply 更新主线程持有的展示状态），再刷新受影响的控件；后台不得直接改展示状态或控件；回调应短且每批有界，不在 UI 中阻塞 `join()` 或等满队列腾位置。
- 保存定时回调标识，关闭时撤销；任务超时、取消、断连及晚到消息遵守原生分支的数据和生命周期契约。无需后台工作的小工具不创建线程或队列。
- 长日志将历史保存与展示条数分开，批量插入/删除可见记录；若达到性能目标需要分页或虚拟化，按真实负载实现，不能靠少显示而改掉导出/持久化的数据契约。
- 指定主题、默认配置与实际依赖集中管理；依赖和资源用项目路径定位，不依赖当前工作目录。字体、DPI 与中文输入在目标 Windows/Linux/macOS 环境核验，不把某台机器的 Tcl 或字体修复写成所有项目的启动要求。

## 效果图与主题

流程按共用入口「界面：效果图先行」。本节只给 ttkbootstrap 的能力边界和落法（2026-10 实测 ttkbootstrap 2.2.3、Pillow 12.3）。

**能力清单**（画效果图前对照，不画第三列）：

| 现成支持 | 需要额外绘制（Canvas / 图片，按成本决定） | 本流程不采用 |
|---|---|---|
| 主题色板（下表 16 个槽位）、bootstyle 变体（实心 / 描边 / 链接、切换开关、条纹进度条）；标准 ttk 控件：按钮、输入框、下拉、复选 / 单选、Notebook、Treeview、Labelframe、Progressbar、Scale、滚动条；grid / pack 布局与内边距；字体族、字号、粗细 | 圆角卡片或面板、渐变、图标（PNG 或图标字体）、自定义形状控件、图表 | 阴影、半透明叠层 / 毛玻璃、过渡动画、逐控件任意圆角半径 |

**DESIGN.md → 主题**：`design_theme.py ttk`（见 vibe-apps「导出」）生成项目根的 `design_tokens.py`，纯数据：`TTK_COLORS`（16 个槽位）、`COLORS`（全部颜色，按 token 名）、`FONTS`（Tk 字体元组，字号已是负数）、`SPACING`、`ROUNDED`。`theme.py` 导入它，用 `ThemeDefinition(name, TTK_COLORS, mode)` 建项目主题，`style.register_theme()` 后 `theme_use()`，再把 `TkDefaultFont` / `TkTextFont` 等命名字体配成 `FONTS` 里的正文字体；色值、字体只从这里来，不手抄。生成器按下表映射槽位，表里要的颜色缺一个就报错。

| DESIGN.md token | ttkbootstrap 槽位 |
|---|---|
| `primary` `secondary` `success` `info` `warning` | 同名 |
| `error` | `danger` |
| `base-100` / `base-content` | `bg` / `fg` |
| `base-200` / `neutral` | `light` / `dark`（深色主题按实际对调） |
| 补的 `selection` / `selection-content` | `selectbg` / `selectfg` |
| 补的 `border`、`input` / `input-content`、`active`（悬停 / 按下） | `border`、`inputbg` / `inputfg`、`active` |

- `accent`、`base-300` 没有槽位，要用就在 Style 里配给具体控件。`*-content` 也没有逐色的槽位：彩色控件上的文字色以框架实际渲染为准，截图对照时核对，不一致就接受框架的颜色或单独配 Style。
- **字号单位**：Tk 正数字号按点、负数按像素。DESIGN.md 的 `16px` 写成 `-16`（生成器已经这样写），写成 `16` 会按点算、明显偏大；2026-10 在 125% 缩放的机器上实测，负数字号仍和效果图同为 12px。Tk 只有常规和粗体，`fontWeight` 只能是 400 / 700。字体族取目标机器上真实存在的那个（Windows 中文默认 `Microsoft YaHei UI`）。
- 间距、内边距按像素填；ttk 没有通用圆角，DESIGN.md 的 `rounded` 只作用于需要额外绘制的部分，整体直角就在正文写明。
- 主题只管颜色和字体，控件自身的尺寸要在 Style 里调：比如 ttkbootstrap 按钮默认的上下内边距在 26px 高度里会切掉文字，要 `style.configure("primary.TButton", padding=(8, 0))` 一类收紧。截图对照时留意这类差异。

**截图**：`root.update()` 等布局稳定后，`PIL.ImageGrab.grab(window=root.winfo_id())` 截客户区，不用按屏幕坐标裁剪（需要 Pillow ≥ 11.2.1）。窗口尺寸用 `geometry()` 固定成效果图的尺寸，样例数据与效果图相同、写死在一个开发入口里。Pillow 只作开发验证依赖，不进交付依赖。

## 开发与交付

- 按宿主约定使用明确的解释器；第三方依赖放项目环境并固定版本，不默认修改全局 Python。
- 默认用 PyInstaller 打包 Python 桌面应用；实际模式与资源清单按分发目标选择。验证图标、字体/图片、主题资源以及路径处理；从不同工作目录启动交付产物。
- 断网启动交付产物，走通核心操作与正常退出，确认没有遗留后台任务。设备依赖仍区分模拟与真实设备测试。
- 低内存与长期运行目标按 `vibe-apps` 实测；Python 打包体积与运行内存分别记录，不以安装包大小推断运行占用。
