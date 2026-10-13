---
name: vibe-apps-native
description: Build or modify native desktop personal apps and hardware control tools after the native route is selected; default Python with ttkbootstrap, or an explicitly selected pure Rust implementation. 原生 GUI、上位机、低内存桌面工具、ttkbootstrap、纯 Rust 桌面。Load vibe-flow and vibe-apps before scaffolding; Web UI uses vibe-apps-web.
---

# vibe-apps-native：原生桌面实现

先遵守 [vibe-apps](../vibe-apps/SKILL.md) 的路线优先级、共用边界、文档标记与资源验收。已选原生时只读当前语言参考：

| 当前实现 | 动手前读 |
|---|---|
| Python，未指定 GUI 时用 ttkbootstrap | [references/python-ttk.md](references/python-ttk.md) |
| 用户已明确选择纯 Rust | [references/rust.md](references/rust.md) |

其他已确认的语言或 GUI 框架沿用项目规范和共用边界，不自动换成默认方案。Python 与 Rust 是实现方案，不要求一个应用同时提供两种语言版本。

## 原生应用的数据流

用户操作 → UI 发起应用操作 → 纯规则计算或后台 IO → 结果/错误事件 → UI 主线程更新展示。短小、无 IO 的计算可直接调用；只有耗时工作才交后台，不默认引入线程池或异步运行时。

- **UI 主线程拥有控件**：后台任务不直接读写控件，通过框架允许的事件通道交回结果。连接、会话、任务与窗口状态各有明确所有者；纯规则不持有窗口或“当前设备”的全局引用。
- **设备/存储 IO 隔离**：阻塞串口读取、网络与磁盘操作交适配器/后台任务，按设备契约设置超时、串行顺序和取消方式。UI 回调不做阻塞等待。
- **背压有契约**：任务和事件队列、内存日志设置适合实际负载的上限。满时明确拒绝、限速或异步等待，不让 UI 主线程阻塞；命令、完成结果、错误和设备回复不得静默丢弃。仅展示刷新可合并，展示日志可限量；原始记录与持久化按项目数据契约处理，不因 UI 裁剪而丢数据。
- **关闭有生命周期**：停止接收新任务，取消或结束后台工作，关闭设备/存储资源，撤销 UI 定时回调；超时或失败按约定提示，不把窗口关闭后的消息投递给已销毁控件。
- **按需刷新**：批量更新展示，长列表只维护可见窗口或适用的虚拟化；不把完整历史每帧重新构造。刷新频率由交互需求决定，不用忙循环维持空闲界面。

## 创建与验证

先建立共用入口要求的 `## 架构约束（vibe-apps）` 段，写明实际原生路线、语言、框架及以上适用的任务/数据约束；按语言参考选最小结构，不要求 `api/`、`web/` 或本地 HTTP 服务。

中文输入、字体与 DPI、键盘/复制、长日志、暂停/恢复、错误提示、断连及退出，用实际窗口走通。硬件类操作没有设备时区分模拟验证与真机结果；验收条件由项目需求决定。打包与性能采样按共用入口及所选语言参考执行。
