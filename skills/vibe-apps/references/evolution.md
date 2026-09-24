# vibe-apps 远期演进：换零件、换语言、变网站

只在真要换框架、换语言，或要把应用变成多人网站时读。平时做应用用不到。

两件事的共同前提都是 SKILL.md 里的头号铁律：**core 对"谁"无状态**。守住它，下面这些都便宜；焊死了，就得回头重写 core。

## 换零件

- **同语言换零件**（FastAPI↔Django、pywebview↔别的窗口库、原生 HTML↔React）= 便宜，core 和 web 不动。
- **换到 Rust/Tauri ≠ 推倒重来**：只要 core 守住"无状态、模块化"，就能用 PyO3 **按模块**把逻辑换成 Rust（Python API 不变、import 姿势照旧）；耐用件（协议编解码、校验、核心算法）甚至可一开始就用 Rust 写、两轨共享。真到分发 / 毕业 Tauri 是**逐模块迁移**，不是整个重写。迁移时机、双轨方案、分发三档见插件 docs `vibe-apps-栈权衡与改进候选.md` §8。
- 判据：换语言不必然贵——**前提是 core 一直保持可 PyO3 化**（这跟"core 对谁无状态"是同一条纪律的白捡收益）。

## 成长为多人网站

同一 `core+api+web`，只换**交付层**：部署 FastAPI 到服务器（丢掉 pywebview/PyInstaller）、`api/` 加登录鉴权、加数据库按用户隔离。`core/` 不动——**前提是它从一开始就对"谁"无状态**。多人 + 登录 + 后台恰是 Django 甜区，也是 FastAPI→Django 便宜 swap 兑现之时。别提前建登录（YAGNI）。
