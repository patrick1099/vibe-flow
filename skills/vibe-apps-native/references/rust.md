# 原生 Rust（Slint）：明确选择时启用

只在用户明确选择纯 Rust，或迁移方向已经按 `vibe-flow` 谈定时读。它是可采用的实现路线，不要求当前 Python 项目提前改写或引入 PyO3/FFI。

**纯 Rust 的含义**：交付应用的业务与 GUI 使用 Rust，不依赖 Python 解释器或 WebView 运行界面；系统库与原生依赖按 Slint 的说明。独立构建/测试工具可以使用 Python，这不改变交付应用的运行时约束。

## 框架：Slint

纯 Rust 原生 GUI 一律用 Slint（用户 2026-10-15 定），不再比较 egui、iced 等其他 Rust GUI，也不为单个项目重新选框架。不因采用 Rust 就宣布更省内存；资源要求仍由 release 产物实测。

- **本机实例**：`my-repos/serial-split`（Slint 1.18，winit + software 渲染，2026-10-14 按确认的样稿做完 v2 界面；2026-10-15 并排对照，布局、控件、颜色、字体还原度高）。可以照它的组件和 Theme 写法起步。
- **界面放哪两种都行**：写在 Rust 文件的 `slint::slint!` 宏里（serial-split 的做法，不用额外构建步骤），或拆成 `.slint` 文件由 `build.rs` 用 `slint-build` 编译（能用 `slint-viewer --auto-reload` 实时预览）。按项目体量和要不要实时预览选，已有项目沿用。
- **本机工具链**：`stable-x86_64-pc-windows-gnullvm`，链接器和 C 编译器用 llvm-mingw；每条 cargo 命令前先把 llvm-mingw 的 `bin` 放到 PATH 最前面，机器内存紧时加 `-j 2`。具体写法见 serial-split 的 README 与 `build.rs`。
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
├── src/
│   ├── main.rs         入口、配置与资源组装
│   ├── core.rs         纯业务规则与数据类型
│   ├── ui.rs           把应用状态接到 Slint 属性与回调；界面、自写小组件与 global Theme（色值只在这里）写在这里的 slint! 宏里，或拆到 ui/*.slint
│   └── adapters.rs     按需：设备、文件、存储等 IO
├── examples/ui_smoke.rs  界面截图夹具：假数据驱动各状态，出快照与效果图对照
└── tests/              按需：行为契约与集成路径
```

按实际体量拆模块；只做一个应用时不用 workspace 或通用 trait 体系。状态与消息用具体类型表达，应用状态可以可变，业务规则不依赖 GUI。多个实际适配成员出现时才按变化轴收口。

## 效果图与主题

流程按共用入口「界面：效果图先行」。Slint 的表现力接近 CSS，效果图可以放开画，但下面第三列仍不画。具体属性名以当时版本的 Slint 文档为准。

| 现成支持（用 `Rectangle` / `Text` / `TextInput` / `PopupWindow` 等基础元素自己拼） | 需要额外处理 | 本流程不采用 |
|---|---|---|
| 圆角、边框、阴影（`drop-shadow-*`）、线性 / 径向渐变、透明度、属性动画（`animate`）、内嵌字体；布局（横 / 竖 / 网格，带间距与内边距）；分组框、方角按钮、下拉、复选、指示灯、标签页、状态栏这类小组件 | 图表和任意形状用 `Path` 画；std-widgets 的 `ScrollView` / `ListView` 可直接当滚动容器，但外观要调成和整体一致 | std-widgets 的 Fluent 默认控件（太高太圆，serial-split v1 “太丑”正是它造成的，v2 改成自写小组件）；背景模糊 / 毛玻璃、CSS filter 一类滤镜（画之前先查当时版本，支持了再放开） |

**DESIGN.md → `global Theme`**：写成 `export global Theme { out property <color> primary: #2563eb; out property <length> space-2: 8px; … }`，token 名照抄 DESIGN.md（Slint 标识符允许连字符）。Slint 的 `px` 是逻辑像素，和 CSS `px` 一一对应，效果图按目标窗口逻辑像素 1:1 画，数值就能直接搬；颜色之外的字体、字号、圆角、间距也都放这里。要浅色 / 深色时在 Theme 里加一个 `dark: bool`，各色按它取值。组件只引用 `Theme.xxx`，不散写色值。生成器还没做，目前由 AI 按 DESIGN.md 手工维护这一份。

**截图**：照 serial-split 的 `examples/ui_smoke.rs`——只用假数据驱动界面，不打开真实串口、不调外部程序；每个要对照的状态用 `Window::take_snapshot()` 出一张图（software 渲染下可用），窗口设成效果图的尺寸、样例数据与效果图相同，断言 `scale_factor() == 1.0` 和预期尺寸，写到 `target/ui-smoke/`（BMP 手写文件头即可，不必为此加图像库依赖）。再和效果图同一状态并排看。

## 后台与构建

- 短小纯计算可直接调用；阻塞 IO 使用后台工作线程或框架支持的任务机制，结果通过事件/消息回到 UI。已有异步需求才选择运行时，不默认引入 Tokio、线程池或每操作一个线程。
- 事件通道与显示历史有界，满时处理、命令/结果/错误不丢弃、关闭取消与释放资源，遵守原生分支的契约；不要在 UI 线程阻塞等待线程退出或通道可写。
- 应用提交 `Cargo.lock`，依赖版本与实际渲染后端可复现；外部 DLL、字体、图标、驱动要求记录并随交付验证。平台特定调用集中在适配处，不放进纯规则。
- 运行 `cargo check`、针对性 `cargo test`，完成项目要求的格式/静态检查，再 `cargo build --release --locked`；从目标机器的交付入口实用验证。资源比较使用 release 构建，不拿 debug 与 Python 打包产物混比。

## 从 Python 迁移

迁移前读共用 [evolution.md](../../vibe-apps/references/evolution.md)，核对协议字节、单位/精度、错误含义、数据格式和可见行为，建立代表性输入与期望输出。

Rust 实现需要重写；Python 源码和测试源码不保证直接复用。可复用的是语言无关的样例、期望结果和行为/数据/验收契约；数据库、文件与协议的兼容性必须单独验证。保留已确认行为，变更行为须由用户决定，不把语言迁移变成顺手重设计。
