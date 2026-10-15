# design_theme 变更记录

## 2026-10-15 出生：DESIGN.md → ttk / Slint 主题生成器

**起因**：效果图先行流程的第二批。用户先定了“原生 GUI 只靠文字需求让 AI 写，观感很差”，界面要先出 HTML 效果图、照图实现，DESIGN.md 作为颜色、字体、间距的唯一来源；第一批只改了 skill 文本，原生主题仍由 AI 按 DESIGN.md 手抄进主题文件。分两批时原定“等真实项目再做”生成器，用户随后说“然后你前面说的第二批也可以开始了”。
**根因**：手抄会抄错、会漂移；designmd 0.4.0 的导出又不是无损转换——无单位 spacing 在 lint 计数和所有导出里都被静默丢掉，dtcg 丢无单位 lineHeight，css-vars 没有字体——只看导出结果发现不了丢了什么，所以校验必须直接读 DESIGN.md 源数据。
**改成**：`py -3 design_theme.py ttk|slint --design DESIGN.md` 读源数据，超出 v1 范围的写法带行号一次列全并拒绝生成；通过后写 ttk 的 `design_tokens.py` 或 Slint 的 `ui/theme.slint`，同时刷新效果图 `index.html` 里 `design-tokens` 块的 CSS 变量；`--check` 查产物是否落后。生成器放插件、产物放应用项目，应用运行和打包不依赖插件或 Node。用同一份 DESIGN.md 做了 HTML 效果图 / ttk / Slint 三方截图验收：取色全等、字号一致。
**没选的路**：无单位 spacing 当像素（codex 建议；规范把无单位数定义为列数或比例，v1 直接报错）；PyYAML 放 venv（codex 建议；插件脚本约定只用 stdlib，分发出去的插件里 venv 无处安置，改为窄子集读取器、子集外报错）；node 脚本调 designmd 的解析器；以 designmd 导出结果为输入（会静默丢字段）；ttk 产物用 JSON（打包要多收一个文件）；单独生成 `theme.css`（本机 Esafenet 加密 python 写出的 `.css`，浏览器读到密文、效果图丢光样式）；效果图 CSS 作为独立目标（不知道要还原到哪个框架，可能用到原生做不出的值）；v1 做深浅色切换。
