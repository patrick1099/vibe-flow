# 原生 Rust（Slint）：明确选择时启用

只在用户明确选择纯 Rust，或迁移方向已经按 `vibe-flow` 谈定时读。它是可采用的实现路线，不要求当前 Python 项目提前改写或引入 PyO3/FFI。

**纯 Rust 的含义**：交付应用的业务与 GUI 使用 Rust，不依赖 Python 解释器或 WebView 运行界面；系统库与原生依赖按 Slint 的说明。独立构建/测试工具可以使用 Python，这不改变交付应用的运行时约束。

## 框架：Slint

纯 Rust 原生 GUI 一律用 Slint（用户 2026-10-15 定），不再比较 egui、iced 等其他 Rust GUI，也不为单个项目重新选框架。不因采用 Rust 就宣布更省内存；资源要求仍由 release 产物实测。

- 界面写在 `.slint` 文件里，由 `build.rs` 用 `slint-build` 编译，Rust 侧 `slint::include_modules!()` 引入；不把大段界面塞进 `slint!` 宏，独立的 `.slint` 文件才能用实时预览。
- 改界面时用 `slint-viewer --auto-reload ui/app.slint` 或编辑器的 Slint 扩展实时预览，不必每次编译整个应用。
- 许可：只自用不分发时不用处理；要分发给别人时，按当时的 Slint 许可条款（GPLv3、免版税许可或商业许可）满足要求，免版税许可有致谢展示的要求，发布前查一次原文。

## 最小适用结构

```text
mytool/
├── AGENTS.md
├── DESIGN.md           界面规范（见 vibe-apps「界面：效果图先行」）
├── docs/{BLUEPRINT.md,CHANGELOG.md}
├── docs/mockup/        定稿的 HTML 效果图
├── Cargo.toml
├── Cargo.lock
├── build.rs            slint-build 编译 ui/
├── ui/
│   ├── app.slint       窗口与界面结构
│   └── theme.slint     按 DESIGN.md 写的 global Theme，色值只在这里
├── src/
│   ├── main.rs         入口、配置与资源组装
│   ├── core.rs         纯业务规则与数据类型
│   ├── ui.rs           把应用状态接到 Slint 属性与回调
│   └── adapters.rs     按需：设备、文件、存储等 IO
└── tests/              按需：行为契约与集成路径
```

按实际体量拆模块；只做一个应用时不用 workspace 或通用 trait 体系。状态与消息用具体类型表达，应用状态可以可变，业务规则不依赖 GUI。多个实际适配成员出现时才按变化轴收口。

## 效果图与主题

流程按共用入口「界面：效果图先行」。Slint 的表现力接近 CSS，效果图可以放开画，但下面第三列仍不画。具体属性名以当时版本的 Slint 文档为准。

| 现成支持 | 需要额外处理 | 本流程不采用 |
|---|---|---|
| 圆角、边框、阴影（`drop-shadow-*`）、线性 / 径向渐变、透明度、属性动画（`animate`）、内嵌字体；布局（横 / 竖 / 网格，带间距与内边距）；std-widgets 的按钮、输入框、下拉、开关、滑块、进度、标签页、列表、表格、滚动区 | std-widgets 自带样式不读你的 Theme：要么用它的调色板全局量调整，要么自绘控件消费 Theme；图表和任意形状用 `Path` 画 | 背景模糊 / 毛玻璃、CSS filter 一类滤镜（画之前先查当时版本，支持了再放开） |

**DESIGN.md → `ui/theme.slint`**：写成 `export global Theme { out property <color> primary: #2563eb; out property <length> space-2: 8px; … }`，token 名照抄 DESIGN.md（Slint 标识符允许连字符）。Slint 的 `px` 是逻辑像素，和 CSS `px` 一一对应，数值直接搬；颜色之外的字体、字号、圆角、间距也都放这里。控件只引用 `Theme.xxx`，不散写色值。生成器还没做，目前由 AI 按 DESIGN.md 手工维护这一份。

**截图**：优先用 `Window::take_snapshot()` 拿窗口内容，渲染后端不支持时退回截系统窗口；固定窗口尺寸和样例数据，注意缩放比与效果图截图一致。

## 后台与构建

- 短小纯计算可直接调用；阻塞 IO 使用后台工作线程或框架支持的任务机制，结果通过事件/消息回到 UI。已有异步需求才选择运行时，不默认引入 Tokio、线程池或每操作一个线程。
- 事件通道与显示历史有界，满时处理、命令/结果/错误不丢弃、关闭取消与释放资源，遵守原生分支的契约；不要在 UI 线程阻塞等待线程退出或通道可写。
- 应用提交 `Cargo.lock`，依赖版本与实际渲染后端可复现；外部 DLL、字体、图标、驱动要求记录并随交付验证。平台特定调用集中在适配处，不放进纯规则。
- 运行 `cargo check`、针对性 `cargo test`，完成项目要求的格式/静态检查，再 `cargo build --release --locked`；从目标机器的交付入口实用验证。资源比较使用 release 构建，不拿 debug 与 Python 打包产物混比。

## 从 Python 迁移

迁移前读共用 [evolution.md](../../vibe-apps/references/evolution.md)，核对协议字节、单位/精度、错误含义、数据格式和可见行为，建立代表性输入与期望输出。

Rust 实现需要重写；Python 源码和测试源码不保证直接复用。可复用的是语言无关的样例、期望结果和行为/数据/验收契约；数据库、文件与协议的兼容性必须单独验证。保留已确认行为，变更行为须由用户决定，不把语言迁移变成顺手重设计。
