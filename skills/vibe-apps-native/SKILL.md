---
name: vibe-apps-native
description: Build or modify native desktop personal apps and hardware control tools after the native route is selected; default Python with ttkbootstrap, or an explicitly selected pure Rust implementation with Slint. 原生 GUI、上位机、低内存桌面工具、ttkbootstrap、纯 Rust 桌面、Slint、照效果图实现原生界面。For direct user work, load vibe-flow and vibe-apps before scaffolding; assigned roles follow vibe-flow/references/role-reading.md; Web UI uses vibe-apps-web.
---

# vibe-apps-native：原生桌面实现

直接服务用户先按 [vibe-apps](../vibe-apps/SKILL.md) 确定路线并遵守共用边界、文档标记与资源验收；已分派角色按 [role-reading.md](../vibe-flow/references/role-reading.md) 只读适用公共部分，沿用已定路线/架构，不通读父入口。已选原生时只读当前语言参考：

| 当前实现 | 动手前读 |
|---|---|
| Python，未指定 GUI 时用 ttkbootstrap | [references/python-ttk.md](references/python-ttk.md) |
| 用户已明确选择纯 Rust（固定 Slint） | [references/rust.md](references/rust.md) |

其他已确认的语言或 GUI 框架沿用项目规范和共用边界，不自动换成默认方案。Python 与 Rust 是实现方案，不要求一个应用同时提供两种语言版本。

**两条路各管什么**（用户 2026-10-15 定）：ttk 管开发敏捷——不用编译，改完即跑，AI 来回改界面最快；Slint 管内存和性能。默认仍是 ttk。ttk 的敏捷有前提：界面只用到 python-ttk.md 能力清单第一列（标准控件、色板）。效果图定稿后若大量落在第二列（自绘控件、圆角卡片、紧凑的自定义列表），在 ttk 里要靠 Canvas 硬画、和 Style 系统较劲，省下的编译时间会被吃掉，Slint（写法接近 CSS）未必更慢——这时用一两句话说明这个后果，问用户换不换 Slint，不替他换，也不展开比较。

界面观感按共用入口「界面：效果图先行」走；所选框架的能力清单、DESIGN.md 颜色怎么对到框架、应用窗口怎么截图，都在语言参考的「效果图与主题」节。

## 原生应用的数据流

先按共用入口讨论架构。以下 application 分工是选定 Clean 分层后的映射，展示状态按共用入口的单向数据流规则；采用更小结构的项目按已定职责裁剪。线程、阻塞、背压和实际退出契约适用于所有原生路线。

用户操作 → 控件回调取输入、调用 application 用例（业务判断不写在回调里）→ 用例执行 domain 规则并通过 ports 调用 IO → 后台结果/错误进入普通数据队列 → UI 线程消费（有跨事件状态时经 apply 更新它）→ 框架绑定或刷新函数更新控件。短小、无 IO 的纯规则可在 UI 线程直接调用，无需空转发用例；只有耗时工作才交后台，不默认引入线程池或异步运行时。

- **UI 主线程拥有控件与可变的展示状态**：后台任务只产生普通数据事件，不直接写展示状态或控件；View 在 UI 线程调度消费事件，需要进展示状态的经 apply 更新，再刷新控件。连接、会话、任务由 application 拥有，展示状态归展示层，控件和窗口绑定由 View 拥有；展示状态与内层都不持有窗口或“当前设备”的全局引用。
- **设备/存储 IO 隔离**：阻塞串口读取、网络与磁盘操作交适配器/后台任务，按设备契约设置超时、串行顺序和取消方式。UI 回调不做阻塞等待。
- **背压有契约**：任务和事件队列、内存日志设置适合实际负载的上限。满时明确拒绝、限速或异步等待，不让 UI 主线程阻塞；命令、完成结果、错误和设备回复不得静默丢弃。仅展示刷新可合并，展示日志可限量；原始记录与持久化按项目数据契约处理，不因 UI 裁剪而丢数据。
- **关闭有生命周期**：View 拦截关闭意图并请求 application，不隐藏到托盘。单进程应用的关窗就是整体退出：退出用例幂等，多次点击或入口兜底复用同一次退出，不重复删除资源；UI 继续处理事件，后台停止接收新任务、取消或结束工作、清理资源，待完成或按约定处理超时/失败后，View 解除订阅、撤销定时绑定并销毁窗口。关窗后还要继续工作的应用按共用入口「关窗即释放界面进程」拆出内核进程：关窗只退出界面进程、不停业务，整体停止才走上述退出用例。UI 不阻塞等待，晚到结果不得写已销毁控件。
- **按需刷新**：批量更新展示，长列表只维护可见窗口或适用的虚拟化；不把完整历史每帧重新构造。刷新频率由交互需求决定，不用忙循环维持空闲界面。

## 创建与验证

先建立共用入口要求的 `## 架构约束（vibe-apps）` 段，写明实际原生路线、语言、框架及以上适用的任务/数据约束；按语言参考选最小结构，不要求 `api/`、`web/` 或本地 HTTP 服务。

第一版主要布局出来就按共用入口截图对照效果图，修完差异再接剩下的业务。中文输入、字体与 DPI、键盘/复制、长日志、暂停/恢复、错误提示、断连及退出，用实际窗口走通。硬件类操作没有设备时区分模拟验证与真机结果；验收条件由项目需求决定。打包与性能采样按共用入口及所选语言参考执行。
