# vibe-apps 远期演进：换零件、变网站

只在真要换框架，或要把应用变成多人网站时读。平时做应用用不到。

两件事的共同前提都是 SKILL.md 里的头号铁律：**core 对"谁"无状态**。守住它，下面这些都便宜；焊死了，就得回头重写 core。

## 换零件

- **后端或壳换零件**（FastAPI↔Django、pywebview↔别的窗口库）= 便宜，core 和 web 不动。
- **前端换框架**（原生 HTML↔React 等）：core 和 api 不动，web 要重写——这正是 web 不放业务逻辑的回报，重写的只是展示。
- 不考虑换语言（Rust/Tauri）：2026-09-29 放弃，自用为主，不为远期迁移牺牲当前体验。

## 成长为多人网站

同一 `core+api+web`，只换**交付层**：部署 FastAPI 到服务器（丢掉 pywebview/PyInstaller）、`api/` 加登录鉴权、加数据库按用户隔离。`core/` 不动——**前提是它从一开始就对"谁"无状态**。多人 + 登录 + 后台恰是 Django 甜区，也是 FastAPI→Django 便宜 swap 兑现之时。别提前建登录（YAGNI）。
