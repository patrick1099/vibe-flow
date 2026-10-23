# 原生 Rust（Slint）：明确选择时启用

只在用户明确选择纯 Rust，或迁移方向已经按 `vibe-flow` 谈定时读。它是可采用的实现路线，不要求当前 Python 项目提前改写或引入 PyO3/FFI。

**纯 Rust 的含义**：交付应用的业务与 GUI 使用 Rust，不依赖 Python 解释器或 WebView 运行界面；系统库与原生依赖按 Slint 的说明。独立构建/测试工具可以使用 Python，这不改变交付应用的运行时约束。

## 框架：Slint

纯 Rust 原生 GUI 一律用 Slint（用户 2026-10-15 定），不再比较 egui、iced 等其他 Rust GUI，也不为单个项目重新选框架。不因采用 Rust 就宣布更省内存；资源要求仍由 release 产物实测。

- **本机实例**：`my-repos/serial-split`（Slint 1.18，winit + software 渲染，2026-10-14 按确认的样稿做完 v2 界面；2026-10-15 并排对照，布局、控件、颜色、字体还原度高）。只参考它的组件和 Theme 写法，不把其 ui.rs 的应用编排方式当成 Clean MVVM 架构样板。
- **界面放哪两种都行**：写在 Rust 文件的 `slint::slint!` 宏里（serial-split 的做法，不用额外构建步骤），或拆成 `.slint` 文件由 `build.rs` 用 `slint-build` 编译（能用 `slint-viewer --auto-reload` 实时预览）。按项目体量和要不要实时预览选，已有项目沿用。
- **本机工具链**：`stable-x86_64-pc-windows-gnullvm`，链接器和 C 编译器用 llvm-mingw；每条 cargo 命令前先把 llvm-mingw 的 `bin` 放到 PATH 最前面，机器内存紧时加 `-j 2`。具体写法见 serial-split 的 README 与 `build.rs`。
- 许可：只自用不分发时不用处理；要分发给别人时，按当时的 Slint 许可条款（GPLv3、免版税许可或商业许可）满足要求，免版税许可有致谢展示的要求，发布前查一次原文。

## 选定 Clean MVVM 时的结构示例

新项目先完成架构讨论。以下骨架仅供选定 Clean MVVM 时使用；简单项目按已定结构裁剪，不为套模板创建空模块。

```text
mytool/
├── AGENTS.md
├── DESIGN.md           界面规范（见 vibe-apps「界面：效果图先行」）
├── docs/{BLUEPRINT.md,CHANGELOG.md}
├── docs/mockup/        定稿的 HTML 效果图
├── Cargo.toml
├── Cargo.lock
├── src/
│   ├── main.rs         入口、配置与资源组装；调用 library 模块
│   ├── lib.rs          导出 core/application/viewmodel；按需导出 ui 供截图夹具调用
│   ├── core.rs         domain：纯业务规则与领域数据
│   ├── application.rs  用例、任务生命周期与外部依赖 ports
│   ├── viewmodel.rs    展示状态、命令；不依赖 Slint/驱动/数据库
│   ├── ui.rs           View：Slint 属性、控件、事件桥与 ViewModel 绑定
│   └── adapters.rs     按需：实现 ports 的设备、文件、存储 IO
├── ui/theme.slint      global Theme，由 DESIGN.md 生成（design_theme.py），不手改
├── examples/ui_smoke.rs  界面截图夹具：假数据驱动各状态，出快照与效果图对照
└── tests/              按需：行为契约与集成路径
```

按实际体量拆模块，遵守 [Clean MVVM](../../vibe-apps/references/clean-mvvm.md)；不为分层强制 Cargo workspace。application 定义实际 IO 所需的窄 trait/函数边界并接受注入，选择泛型或 trait object 按实际用途，不造通用仓储基类。Slint 的 Weak、ModelRc、SharedString 和回调绑定只在 View/界面适配处；ViewModel 用普通 Rust 状态与消息，可不启动 Slint 测试。串口线程生命周期和退出清理由 application 协调，不因独立成一个 App struct 就仍放在 ui.rs。

单个 crate 的模块划分并不能在编译期禁止所有反向依赖。集成测试与 examples 从 `lib.rs` 导出的公共接口调用，避免在二进制和夹具重复声明同一套模块；公开的内层接口不泄漏 Slint 类型。需要强编译隔离时再讨论拆 crate，否则使用约定的静态依赖检查。ViewModel 测试可使用真实用例加假 port，或注入普通结果事件，不要求每个用例都有一份 trait。

## 效果图与主题

流程按共用入口「界面：效果图先行」。Slint 的表现力接近 CSS，效果图可以放开画，但下面第三列仍不画。具体属性名以当时版本的 Slint 文档为准。

| 现成支持（用 `Rectangle` / `Text` / `TextInput` / `PopupWindow` 等基础元素自己拼） | 需要额外处理 | 本流程不采用 |
|---|---|---|
| 圆角、边框、阴影（`drop-shadow-*`）、线性 / 径向渐变、透明度、属性动画（`animate`）、内嵌字体；布局（横 / 竖 / 网格，带间距与内边距）；分组框、方角按钮、下拉、复选、指示灯、标签页、状态栏这类小组件 | 图表和任意形状用 `Path` 画；std-widgets 的 `ScrollView` / `ListView` 可直接当滚动容器，但外观要调成和整体一致 | std-widgets 的 Fluent 默认控件（太高太圆，serial-split v1 “太丑”正是它造成的，v2 改成自写小组件）；背景模糊 / 毛玻璃、CSS filter 一类滤镜（画之前先查当时版本，支持了再放开） |

**DESIGN.md → `global Theme`**：`design_theme.py slint`（见 vibe-apps「导出」）生成 `ui/theme.slint`，内容是 `export global Theme { … }`：颜色照抄 token 名（`Theme.primary`、`Theme.base-100`），其余加前缀（`Theme.spacing-md`、`Theme.rounded-sm`、`Theme.<字体名>-family|size|weight`）。界面写在 `slint!` 宏里也能用它：宏内 `import { Theme } from "ui/theme.slint";`，路径相对 crate 根，改了这个文件 cargo 会自动重编（Slint 1.18.1 实测）；拆成 `.slint` 文件的项目照常 import。Slint 的 `px` 是逻辑像素，和 CSS `px` 一一对应，效果图按目标窗口逻辑像素 1:1 画，数值就能直接搬。组件只引用 `Theme.xxx`，不散写色值。生成器只出一套颜色；要浅色 / 深色切换的项目（如 serial-split 的 `dark: bool`）照旧手写 Theme，不接生成器。
- **字体文件要注册全**：software 渲染器不会合成粗体。用到 `fontWeight: 700` 就得把粗体文件也注册上（微软雅黑是 `msyhbd.ttc`，常规体是 `msyh.ttc`），否则粗体静默按常规体画，截图对照时才看得出来（2026-10 实测）。

**截图**：照 serial-split 的 `examples/ui_smoke.rs`——只用假数据驱动界面，不打开真实串口、不调外部程序；每个要对照的状态用 `Window::take_snapshot()` 出一张图（software 渲染下可用），窗口设成效果图的尺寸、样例数据与效果图相同，写到 `target/ui-smoke/`（BMP 手写文件头即可，不必为此加图像库依赖）。系统缩放不是 100% 时，先设环境变量 `SLINT_SCALE_FACTOR=1`（serial-split 在夹具入口里设），再断言 `scale_factor() == 1.0` 和预期尺寸。再和效果图同一状态并排看。

## 后台与构建

- 短小纯计算可直接调用；阻塞 IO 使用后台工作线程或框架支持的任务机制，结果通过普通事件/消息回到 UI。View 用 UI 线程的 Timer 消费，或安全唤醒后消费队列，先更新同线程拥有的 ViewModel 再绑定；后台不持有可变 ViewModel，不默认用 Arc<Mutex<ViewModel>>。已有异步需求才选择运行时，不默认引入 Tokio、线程池或每操作一个线程。
- 事件通道与显示历史有界，满时处理、命令/结果/错误不丢弃、关闭取消与释放资源，遵守原生分支的契约；不要在 UI 线程阻塞等待线程退出或通道可写。
- 应用提交 `Cargo.lock`，依赖版本与实际渲染后端可复现；外部 DLL、字体、图标、驱动要求记录并随交付验证。平台特定调用集中在适配处，不放进纯规则。
- 运行 `cargo check`、针对性 `cargo test`，完成项目要求的格式/静态检查，再 `cargo build --release --locked`；从目标机器的交付入口实用验证。资源比较使用 release 构建，不拿 debug 与 Python 打包产物混比。

## 从 Python 迁移

迁移前读共用 [evolution.md](../../vibe-apps/references/evolution.md)，核对协议字节、单位/精度、错误含义、数据格式和可见行为，建立代表性输入与期望输出。

Rust 实现需要重写；Python 源码和测试源码不保证直接复用。可复用的是语言无关的样例、期望结果和行为/数据/验收契约；数据库、文件与协议的兼容性必须单独验证。保留已确认行为，变更行为须由用户决定，不把语言迁移变成顺手重设计。
