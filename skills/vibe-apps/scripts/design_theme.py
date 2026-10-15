# 结构: vibe-scripts/standard
# 用途: 读项目根 DESIGN.md 的 token，校验后生成原生主题文件（ttk 的 design_tokens.py 或 Slint 的 ui/theme.slint），并刷新效果图 HTML 里的 token 样式块
# 用法: py -3 design_theme.py ttk|slint [--design DESIGN.md] [--out 路径] [--mockup 路径] [--check | --dry-run]
# 原始需求: 效果图先行第二批——DESIGN.md → ttk / Slint 主题生成器；生成器放插件、产物放项目、不支持的字段报错不静默丢；
#           校验必须看 DESIGN.md 源数据（designmd 0.4.0 的导出会静默丢无单位 spacing 等），只用 stdlib。
"""DESIGN.md → 原生主题生成器。

只在改设计时由 AI 跑；生成结果提交进应用项目，应用运行、打包不依赖本插件或 Node。
一次产出两处：目标框架的主题文件；效果图 docs/mockup/index.html 里 <style id="design-tokens"> 块的 CSS 变量。
两处出自同一次校验，效果图因此用不到目标框架还原不了的值。

token 写进 HTML 而不是单独的 theme.css：本机 Esafenet 会把 python 写出的 .css 加密，浏览器读到密文、
效果图失去全部样式（2026-10-15 实测）；.html 不受影响，单文件效果图也最好分发。

输出一行 JSON 信封；退出码 0 成功，1 运行失败（DESIGN.md 不合要求、--check 发现产物过期、读写失败），
2 参数错误。完整说明见 --ai-help。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

# ===== 1 配置/常量 =====

MOCKUP = "docs/mockup/index.html"
# 效果图里由本工具维护的样式块；块外的 HTML 是手写的，不碰
TOKEN_BLOCK = re.compile(r'(<style id="design-tokens">)(.*?)(</style>)', re.S)

# 顶层字段：生成要用的 token 段；不参与生成、整块跳过的段；v1 明确不支持的段
TOKEN_SECTIONS = ("colors", "typography", "rounded", "spacing")
SKIP_SECTIONS = ("version", "name", "description", "omitted", "components")
UNSUPPORTED_SECTIONS = {
    "components": "components 段 v1 不支持：生成器只出颜色、字体、间距、圆角；原生项目的 DESIGN.md 不写 components，"
                  "控件样式在主题里按这些 token 配",
}
UNSUPPORTED_TYPO = {
    "lineHeight": "lineHeight v1 不支持：Tk 标签没有行高，Slint 的 line-height-factor 乘的是字体自然行高而不是字号，"
                  "含义对不上；删掉它，行距在用到的控件里按效果图单独调",
    "letterSpacing": "letterSpacing v1 不支持：Tk 没有字间距",
    "fontFeature": "fontFeature v1 不支持：原生框架不认 font-feature-settings",
    "fontVariation": "fontVariation v1 不支持：原生框架不认 font-variation-settings",
}
GENERATED_NOTE = "由 design_theme.py 从 DESIGN.md 生成，勿手改；改设计就改 DESIGN.md 再重新生成"

AI_HELP = """---
name: design_theme
description: 从项目根 DESIGN.md 生成原生主题（ttk 的 design_tokens.py / Slint 的 ui/theme.slint），并刷新效果图 HTML 里的 token 块
ai_help_version: 1
---

# design_theme

## Quick Reference

```
py -3 design_theme.py ttk --design <项目>/DESIGN.md             # 写 design_tokens.py，刷新效果图里的 token 块
py -3 design_theme.py slint --design <项目>/DESIGN.md --check   # 只核对产物是否和 DESIGN.md 一致
```

从别的程序调用时用 list argv（`subprocess.run([...])`），不要拼命令行字符串。

## When to Use

原生应用（ttk / Slint）改了 DESIGN.md 之后。先跑 `designmd lint DESIGN.md` 查规范，再跑本工具。
Web 路线不用本工具，仍用 `designmd export`。

## Command Reference

- `<target>`（必填）：`ttk` 或 `slint`。
- `--design PATH`（可选，默认 `./DESIGN.md`）。
- `--out PATH`（可选）：主题文件路径；默认相对 DESIGN.md 所在目录，ttk 为 `design_tokens.py`，slint 为 `ui/theme.slint`。
- `--mockup PATH`（可选）：效果图 HTML，默认相对 DESIGN.md 所在目录的 `docs/mockup/index.html`。
  HTML 的 `<head>` 里要有一个 `<style id="design-tokens"></style>`，工具只替换这个块的内容
  （`:root` 上的 `--color-*`、`--spacing-*`、`--rounded-*`、`--font-<名>-family|size|weight`）；
  文件不存在就跳过（`status: skipped`），文件在但没有这个块报错。
- `--check`（可选）：不写文件，产物缺失或与 DESIGN.md 不一致即失败（退出 1）。
- `--dry-run`（可选）：不写文件，`data.files[].status` 报告会怎样变化，退出 0。
- `--json` / `--format json`：接受但无作用，输出始终是 JSON。

## 支持范围（v1）

- 颜色：`#RGB` / `#RRGGBB`；slint 另接受 `#RRGGBBAA`。`rgb()`、颜色名等先换算成 hex。
- 尺寸（spacing、rounded、fontSize）：只认 `px`；无单位数和 em/rem 报错。
- typography：`fontFamily`（单个字体族）、`fontSize`（必填）、`fontWeight`（缺省 400；ttk 只接 400/700）。
  `lineHeight`、`letterSpacing`、`fontFeature`、`fontVariation` 报错。
- `components` 段报错。`version`、`name`、`description`、`omitted` 不参与生成。
- ttk 必须定义 16 个槽位要的颜色：primary secondary success info warning error base-100 base-content
  base-200 neutral selection selection-content border input input-content active；字号、间距、圆角要整数 px。
- front matter 只认块状写法：缩进用空格；不认锚点、`{}` / `[]` 行内写法、`|` / `>` 多行块（这些只能出现在不参与生成的段里）。
  以 `#` 开头的颜色值必须加引号，否则 YAML 当注释。

## Side Effects & Safety

写主题文件（按需建父目录），改写效果图 HTML 里的 token 块（块外一字不动，保留原换行风格）；
先写同目录临时文件再替换，内容不变的文件不重写。
`--check`、`--dry-run` 不写任何文件。不联网，不调外部程序。

## Exit Codes

- 0：成功（含 `--dry-run`）。
- 1：DESIGN.md 不合要求（`E_VALIDATION`）、DESIGN.md 不存在（`E_NOT_FOUND`）、`--check` 发现产物过期（`E_VERIFICATION_FAILED`）、读写失败（`E_IO` / `E_PERMISSION`）。
- 2：参数错误（`E_VALIDATION`）。

## Errors & Recovery

- `E_VALIDATION` 且退出 1：`error.details.problems` 逐条列出（行号、位置、原因），按条改 DESIGN.md 后重跑。
- `E_VERIFICATION_FAILED`：不带 `--check` 重跑一次生成，再提交产物。
- `E_VALIDATION` 且提到 design-tokens：在效果图 `<head>` 里加 `<style id="design-tokens"></style>` 后重跑。
- 颜色值被报“当成注释”：给值加引号，`primary: "#2563eb"`。
"""

# ===== 3 Core：纯逻辑（解析、校验、渲染；不碰文件、不 print）=====

Leaf = namedtuple("Leaf", "value line")
Problem = namedtuple("Problem", "line where message")

KEY_LINE = re.compile(r"([A-Za-z0-9_-]+)[ ]*:(?:[ ]+(.*))?$")
INT = re.compile(r"-?(0|[1-9][0-9]*)")
FLOAT = re.compile(r"-?(0|[1-9][0-9]*)\.[0-9]+")
AMBIGUOUS = {"true", "false", "yes", "no", "on", "off", "null", "~"}
HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
HEX_ALPHA = re.compile(r"#([0-9a-fA-F]{4}|[0-9a-fA-F]{8})")
PX = re.compile(r"(0|[1-9][0-9]*)(\.[0-9]+)?px")
REL_UNIT = re.compile(r"[0-9.]+(em|rem)")


class DesignError(Exception):
    def __init__(self, problems):
        super().__init__(f"DESIGN.md 有 {len(problems)} 处不合要求")
        self.problems = problems


def split_front_matter(text):
    """返回 (front matter 各行, 第一行的行号)。规范要求开头和结尾各一行只有 ---。"""
    lines = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0].rstrip() != "---":
        raise DesignError([Problem(1, "", "开头没有 --- 包起来的 front matter（token 都写在那里）")])
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return lines[1:i], 2
    raise DesignError([Problem(1, "", "front matter 没有结束的 --- 行")])


def parse_scalar(text):
    """解析一个标量，返回 (值, 错误信息)。只认引号字符串、整数、小数、普通字符串。"""
    if text.startswith("#"):
        return None, "值以 # 开头会被 YAML 当成注释，要加引号，如 \"#2563eb\""
    if text[0] in "\"'":
        quote, i = text[0], 1
        while i < len(text):
            if quote == '"' and text[i] == "\\":
                i += 2
                continue
            if text[i] == quote:
                if quote == "'" and text[i + 1:i + 2] == "'":
                    i += 2
                    continue
                break
            i += 1
        else:
            return None, "引号没有闭合"
        rest = text[i + 1:].strip()
        if rest and not rest.startswith("#"):
            return None, "引号字符串后面还有多余内容"
        if quote == "'":
            return text[1:i].replace("''", "'"), None
        try:
            return json.loads(text[:i + 1]), None
        except ValueError:
            return None, "双引号字符串里的转义只认 JSON 那几种（\\\" \\\\ \\n \\uXXXX）"
    if text[0] in "[]{}&*!|>%@`,?":
        return None, "不支持这种 YAML 写法（行内 [] {}、锚点、| > 多行块等）；改成块状写法或加引号"
    cut = text.find(" #")
    plain = (text[:cut] if cut >= 0 else text).rstrip()
    if ": " in plain or plain.endswith(":"):
        return None, "一行里只能写一个键值"
    if plain.lower() in AMBIGUOUS:
        return None, f"{plain} 在 YAML 里会被当成布尔或空值，要当文字就加引号"
    if INT.fullmatch(plain):
        return int(plain), None
    if FLOAT.fullmatch(plain):
        return float(plain), None
    return plain, None


def parse_front_matter(lines, first_line):
    """把 front matter 解析成嵌套 dict（叶子是 Leaf）。只认块状映射；子集之外的写法逐条报错。

    SKIP_SECTIONS 里的段整块跳过不解析（它们可能用到多行块、行内列表等写法），只记一个 Leaf 表示存在。
    """
    root, problems = {}, []
    stack = [(-1, root, "")]          # (缩进, 节点, 路径)
    kid_indent = {"": 0}              # 每个映射的子项缩进，必须一致
    skipping = False
    for offset, raw in enumerate(lines):
        line = first_line + offset
        body = raw.rstrip()
        stripped = body.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(body) - len(stripped)
        if skipping:
            if indent > 0 or stripped.startswith("-"):
                continue
            skipping = False
        if stripped.startswith("\t"):
            problems.append(Problem(line, "", "缩进不能用 tab，用空格"))
            continue
        if stripped.startswith("-"):
            problems.append(Problem(line, "", "列表只能出现在 omitted 段里"))
            continue
        m = KEY_LINE.match(stripped)
        if not m:
            problems.append(Problem(line, "", "看不懂这一行：只认 `键: 值` 或 `键:`，键名用字母、数字、- 和 _，不加引号"))
            continue
        while stack[-1][0] >= indent:
            stack.pop()
        _, node, path = stack[-1]
        expected = kid_indent.setdefault(path, indent)
        if indent != expected:
            problems.append(Problem(line, path, f"缩进不一致：这一层应缩进 {expected} 个空格"))
            continue
        key, value = m.group(1), m.group(2)
        where = f"{path}.{key}" if path else key
        if key in node:
            problems.append(Problem(line, where, "键重复了"))
            continue
        if path == "" and key in SKIP_SECTIONS:
            node[key] = Leaf(value, line)
            skipping = True
            continue
        if value is not None and value.startswith("#") and not (HEX.fullmatch(value) or HEX_ALPHA.fullmatch(value)):
            value = None              # `键: # 注释`，等于没写值；像色值的留给 parse_scalar 报“要加引号”
        if value is None:
            child = {}
            node[key] = child
            stack.append((indent, child, where))
            continue
        scalar, error = parse_scalar(value)
        if error:
            problems.append(Problem(line, where, error))
            continue
        node[key] = Leaf(scalar, line)
    return root, problems


def _px(leaf, where, problems, unitless_hint):
    v = leaf.value
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        problems.append(Problem(leaf.line, where, unitless_hint))
        return None
    if isinstance(v, str):
        m = PX.fullmatch(v.strip())
        if m:
            n = float(m.group(0)[:-2])
            return int(n) if n.is_integer() else n
        if REL_UNIT.fullmatch(v.strip()):
            problems.append(Problem(leaf.line, where, "em / rem 换不成原生像素，v1 只认 px"))
            return None
    problems.append(Problem(leaf.line, where, "尺寸只认 px，如 8px"))
    return None


def _color(leaf, where, problems):
    v = leaf.value
    if isinstance(v, str):
        s = v.strip()
        for pattern in (HEX, HEX_ALPHA):
            if pattern.fullmatch(s):
                digits = s[1:]
                if len(digits) in (3, 4):
                    digits = "".join(c * 2 for c in digits)
                return "#" + digits.lower()
    problems.append(Problem(leaf.line, where, "颜色只认 #RGB / #RRGGBB（带透明度写 #RRGGBBAA）；rgb()、颜色名等先换算成 hex"))
    return None


def _section(root, name, problems):
    node = root.get(name, {})
    if isinstance(node, Leaf):
        problems.append(Problem(node.line, name, f"{name} 应该是映射（下一行起缩进写 token）"))
        return {}
    return node


def build_model(root):
    """把解析树规整成内部模型，并做与目标无关的校验。返回 (model, problems)。

    model: colors{名: "#rrggbb" 或 "#rrggbbaa"}、typography{名: {family, size, weight}}、
           spacing{名: px}、rounded{名: px}；lines{"段.名": 行号} 给目标校验报行号用。
    """
    problems = []
    for key, node in root.items():
        line = node.line if isinstance(node, Leaf) else None
        if key in UNSUPPORTED_SECTIONS:
            problems.append(Problem(line, key, UNSUPPORTED_SECTIONS[key]))
        elif key not in TOKEN_SECTIONS and key not in SKIP_SECTIONS:
            problems.append(Problem(line, key, "不认识的顶层字段（规范只有 version name description omitted colors typography rounded spacing components）"))
    model = {"colors": {}, "typography": {}, "spacing": {}, "rounded": {}, "lines": {}}

    def leaves(section):
        for name, node in _section(root, section, problems).items():
            where = f"{section}.{name}"
            if isinstance(node, Leaf):
                model["lines"][where] = node.line
                yield name, where, node
            else:
                problems.append(Problem(None, where, "这里应该直接写值，不是再嵌一层"))

    for name, where, leaf in leaves("colors"):
        value = _color(leaf, where, problems)
        if value:
            model["colors"][name] = value
    for section in ("spacing", "rounded"):
        hint = ("无单位数在规范里表示列数或比例，不是像素；原生主题要 px，写成 8px" if section == "spacing"
                else "圆角要写单位，如 4px")
        for name, where, leaf in leaves(section):
            value = _px(leaf, where, problems, hint)
            if value is not None:
                model[section][name] = value

    for name, node in _section(root, "typography", problems).items():
        where = f"typography.{name}"
        if isinstance(node, Leaf):
            problems.append(Problem(node.line, where, "typography 的每一项要写成映射：fontFamily / fontSize / fontWeight"))
            continue
        style, line = {}, None
        for prop, leaf in node.items():
            pw = f"{where}.{prop}"
            if not isinstance(leaf, Leaf):
                problems.append(Problem(None, pw, "这里应该直接写值"))
                continue
            line = line or leaf.line
            if prop in UNSUPPORTED_TYPO:
                problems.append(Problem(leaf.line, pw, UNSUPPORTED_TYPO[prop]))
            elif prop == "fontFamily":
                family = leaf.value if isinstance(leaf.value, str) else None
                if not family or not family.strip():
                    problems.append(Problem(leaf.line, pw, "fontFamily 要写字体名"))
                elif "," in family:
                    problems.append(Problem(leaf.line, pw, "只写一个字体族：原生框架不认 CSS 那种逗号分隔的回退列表"))
                elif any(ord(c) < 32 for c in family):
                    problems.append(Problem(leaf.line, pw, "字体名里不能有换行等控制字符"))
                else:
                    style["family"] = family.strip()
            elif prop == "fontSize":
                size = _px(leaf, pw, problems, "fontSize 要写单位，如 14px")
                if size is not None:
                    style["size"] = size
            elif prop == "fontWeight":
                w = leaf.value
                if isinstance(w, str) and w.strip().isdigit():
                    w = int(w.strip())
                if isinstance(w, int) and not isinstance(w, bool) and 100 <= w <= 900 and w % 100 == 0:
                    style["weight"] = w
                else:
                    problems.append(Problem(leaf.line, pw, "fontWeight 只认 100–900 的整百数，如 400、700"))
            else:
                problems.append(Problem(leaf.line, pw, "不认识的 typography 属性（规范有 fontFamily fontSize fontWeight lineHeight letterSpacing fontFeature fontVariation）"))
        model["lines"][where] = line
        for need, label in (("family", "fontFamily"), ("size", "fontSize")):
            if need not in style and not any(p.where == f"{where}.{label}" for p in problems):
                problems.append(Problem(line, where, f"缺 {label}"))
        if "family" in style and "size" in style:
            style.setdefault("weight", 400)
            model["typography"][name] = style
    return model, problems


def load_model(text):
    """DESIGN.md 全文 → (model, 源摘要)。不合要求时抛 DesignError，带全部问题。

    源摘要只取 front matter（换行归一后），改正文不算设计变了。
    """
    lines, first = split_front_matter(text)
    root, problems = parse_front_matter(lines, first)
    model, more = build_model(root)
    problems += more
    if problems:
        raise DesignError(problems)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]
    return model, digest


def _quoted(s):
    """CSS 与 Slint 的字符串字面量：两者都用反斜杠转义引号和反斜杠。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_css(model, digest):
    out = [f"/* {GENERATED_NOTE}。source-sha256: {digest} */", ":root {"]
    out += [f"  --color-{n}: {v};" for n, v in model["colors"].items()]
    out += [f"  --spacing-{n}: {v}px;" for n, v in model["spacing"].items()]
    out += [f"  --rounded-{n}: {v}px;" for n, v in model["rounded"].items()]
    for n, s in model["typography"].items():
        out += [f"  --font-{n}-family: {_quoted(s['family'])};",
                f"  --font-{n}-size: {s['size']}px;",
                f"  --font-{n}-weight: {s['weight']};"]
    out.append("}")
    return "\n".join(out) + "\n"


# --- ttk 适配器 ---

# ttkbootstrap 2.2.3 的 Colors(...) 16 个槽位全部必填；映射照 vibe-apps-native/references/python-ttk.md
TTK_SLOTS = {
    "primary": "primary", "secondary": "secondary", "success": "success", "info": "info",
    "warning": "warning", "danger": "error", "bg": "base-100", "fg": "base-content",
    "light": "base-200", "dark": "neutral", "selectbg": "selection", "selectfg": "selection-content",
    "border": "border", "inputbg": "input", "inputfg": "input-content", "active": "active",
}
TTK_WEIGHTS = {400: "normal", 700: "bold"}


def check_ttk(model):
    problems, lines = [], model["lines"]
    missing = [t for t in TTK_SLOTS.values() if t not in model["colors"]]
    if missing:
        problems.append(Problem(None, "colors", "ttkbootstrap 的 16 个颜色槽位都要有值，还缺：" + " ".join(missing)))
    for n, v in model["colors"].items():
        if len(v) == 9:
            problems.append(Problem(lines.get(f"colors.{n}"), f"colors.{n}", "ttk 没有透明度，颜色只能写 #RRGGBB"))
    for n, s in model["typography"].items():
        where = f"typography.{n}"
        if s["weight"] not in TTK_WEIGHTS:
            problems.append(Problem(lines.get(where), where, "Tk 只有常规和粗体，fontWeight 只能是 400 或 700"))
        if not isinstance(s["size"], int):
            problems.append(Problem(lines.get(where), where, "Tk 字号要整数像素"))
    for section in ("spacing", "rounded"):
        for n, v in model[section].items():
            if not isinstance(v, int):
                problems.append(Problem(lines.get(f"{section}.{n}"), f"{section}.{n}", "Tk 的尺寸要整数像素"))
    return problems


def render_ttk(model, digest):
    def block(name, items, comment):
        rows = [f"# {comment}", f"{name} = {{"]
        rows += [f"    {k!r}: {v!r}," for k, v in items]
        return rows + ["}", ""]

    out = [f"# {GENERATED_NOTE}。", f"# source-sha256: {digest}", ""]
    out += block("TTK_COLORS", [(slot, model["colors"][token]) for slot, token in TTK_SLOTS.items()],
                 "ttkbootstrap 的 16 个颜色槽位：ThemeDefinition(name, TTK_COLORS, mode)")
    out += block("COLORS", model["colors"].items(), "DESIGN.md 的全部颜色，按 token 名取；没有槽位的（accent、base-300、*-content）在 Style 里配给具体控件")
    out += block("FONTS", [(n, (s["family"], -s["size"], TTK_WEIGHTS[s["weight"]])) for n, s in model["typography"].items()],
                 "Tk 字体元组：字号写负数表示像素")
    out += block("SPACING", model["spacing"].items(), "间距，像素")
    out += block("ROUNDED", model["rounded"].items(), "圆角，像素；ttk 控件没有通用圆角，只给额外绘制的部分用")
    return "\n".join(out).rstrip("\n") + "\n"


# --- Slint 适配器 ---

SLINT_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def _slint_names(model):
    """Theme 里每个属性的 (生成名, 来源)，渲染和查重共用。"""
    names = [(n, f"colors.{n}") for n in model["colors"]]
    names += [(f"spacing-{n}", f"spacing.{n}") for n in model["spacing"]]
    names += [(f"rounded-{n}", f"rounded.{n}") for n in model["rounded"]]
    for n in model["typography"]:
        names += [(f"{n}-{part}", f"typography.{n}") for part in ("family", "size", "weight")]
    return names


def check_slint(model):
    problems, seen = [], {}
    for name, where in _slint_names(model):
        line = model["lines"].get(where)
        if not SLINT_IDENT.fullmatch(name):
            problems.append(Problem(line, where, f"生成的属性名 {name} 不是合法的 Slint 标识符（要以字母或 _ 开头）"))
        key = name.replace("_", "-")
        if key in seen and seen[key] != where:
            problems.append(Problem(line, where, f"生成的属性名 {name} 和 {seen[key]} 重名（Slint 里 _ 与 - 等价）"))
        seen.setdefault(key, where)
    return problems


def render_slint(model, digest):
    out = [f"// {GENERATED_NOTE}。", f"// source-sha256: {digest}", "", "export global Theme {"]
    out += [f"    out property <color> {n}: {v};" for n, v in model["colors"].items()]
    out += [f"    out property <length> spacing-{n}: {v}px;" for n, v in model["spacing"].items()]
    out += [f"    out property <length> rounded-{n}: {v}px;" for n, v in model["rounded"].items()]
    for n, s in model["typography"].items():
        out += [f"    out property <string> {n}-family: {_quoted(s['family'])};",
                f"    out property <length> {n}-size: {s['size']}px;",
                f"    out property <int> {n}-weight: {s['weight']};"]
    out.append("}")
    return "\n".join(out) + "\n"


# 输出目标这条变化轴的唯一名单：加或去掉一个目标只动它的适配器和这张表
TARGETS = {
    "ttk": {"out": "design_tokens.py", "check": check_ttk, "render": render_ttk},
    "slint": {"out": "ui/theme.slint", "check": check_slint, "render": render_slint},
}


def generate(text, target):
    """DESIGN.md 全文 → (主题文件默认相对路径, 主题文件内容, 效果图 CSS)；目标校验不过时抛 DesignError。"""
    model, digest = load_model(text)
    adapter = TARGETS[target]
    problems = adapter["check"](model)
    if problems:
        raise DesignError(problems)
    return adapter["out"], adapter["render"](model, digest), render_css(model, digest)


class MockupError(Exception):
    pass


def inject_tokens(html, css):
    """把 CSS 换进效果图的 design-tokens 块，块外原样保留；换行风格跟随原文件。"""
    blocks = TOKEN_BLOCK.findall(html)
    if len(blocks) != 1:
        raise MockupError('效果图 HTML 里要有且只有一个 <style id="design-tokens"></style>'
                          f"（现在有 {len(blocks)} 个）")
    eol = "\r\n" if "\r\n" in html else "\n"
    body = eol + css.replace("\n", eol)
    return TOKEN_BLOCK.sub(lambda m: m.group(1) + body + m.group(3), html)


# ===== 4 Adapter：文件读写 =====

def read_text(path):
    """按 UTF-8 读，保留原换行。"""
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def write_output(path, content, dry_run):
    """写一份产物；dry_run 时只报告会怎样变化。预演与真写走这同一个函数。

    比较时不计 CRLF / LF 之别（git 检出可能改换行），写入时内容原样落盘。
    """
    old = read_text(path).replace("\r\n", "\n") if path.exists() else None
    status = "created" if old is None else ("unchanged" if old == content.replace("\r\n", "\n") else "updated")
    if status != "unchanged" and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 临时文件保留目标的扩展名：Esafenet 拒绝把别的扩展名改名成受加密的扩展名（.py / .css，WinError 17）
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=f".tmp{path.suffix}")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    return status


# ===== 5 App：CLI 入口（调度组合、负责输出）=====

class UsageError(Exception):
    pass


class StaleError(Exception):
    def __init__(self, files):
        super().__init__("产物缺失或与 DESIGN.md 不一致")
        self.files = files


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def _emit(ok, data=None, error=None):
    envelope = {"ok": ok, "data": data, "error": error, "meta": {}}
    stream = sys.stdout if ok else sys.stderr
    stream.write(json.dumps(envelope, ensure_ascii=False) + "\n")


def _fail(code, message, suggestion, details=None, exit_code=1):
    _emit(False, error={"code": code, "message": message, "details": details or {},
                        "retryable": False, "suggestion": suggestion})
    return exit_code


def _io_code(exc):
    while exc is not None:
        if isinstance(exc, FileNotFoundError):
            return "E_NOT_FOUND"
        if isinstance(exc, PermissionError):
            return "E_PERMISSION"
        if isinstance(exc, OSError):
            return "E_IO"
        exc = exc.__cause__
    return None


def run(args):
    design = Path(args.design).resolve()
    text = design.read_bytes().decode("utf-8")
    base = design.parent
    dry_run = args.dry_run or args.check
    theme_rel, theme, css = generate(text, args.target)
    theme_path = Path(args.out).resolve() if args.out else base / theme_rel
    mockup_path = Path(args.mockup).resolve() if args.mockup else base / MOCKUP
    files = [{"kind": "theme", "path": str(theme_path), "status": write_output(theme_path, theme, dry_run)}]
    if mockup_path.exists():
        html = inject_tokens(read_text(mockup_path), css)
        files.append({"kind": "mockup", "path": str(mockup_path), "status": write_output(mockup_path, html, dry_run)})
    else:
        files.append({"kind": "mockup", "path": str(mockup_path), "status": "skipped", "reason": "效果图 HTML 不存在"})
    if args.check and any(f["status"] not in ("unchanged", "skipped") for f in files):
        raise StaleError(files)
    return {"target": args.target, "design": str(design), "dry_run": bool(args.dry_run or args.check),
            "check": args.check, "files": files}


def main(argv=None):
    # Windows 控制台默认 GBK，信封里的中文会乱码，统一按 UTF-8 输出
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    head = argv[:argv.index("--")] if "--" in argv else argv
    if "--ai-help" in head:
        sys.stdout.write(AI_HELP)
        return 0
    parser = Parser(prog="design_theme.py", description="DESIGN.md → 原生主题（ttk / Slint）与效果图 CSS",
                    epilog="LLMs/agents: run 'design_theme.py --ai-help' for usage guidance.")
    parser.add_argument("target", choices=list(TARGETS), help="目标框架")
    parser.add_argument("--design", default="DESIGN.md", help="DESIGN.md 路径，默认当前目录下的")
    parser.add_argument("--out", help="主题文件路径，默认相对 DESIGN.md 所在目录")
    parser.add_argument("--mockup", help="效果图 HTML，默认 <DESIGN.md 目录>/" + MOCKUP)
    parser.add_argument("--check", action="store_true", help="不写文件，产物过期即失败")
    parser.add_argument("--dry-run", action="store_true", help="不写文件，只报告会怎样变化")
    parser.add_argument("--json", action="store_true", help="接受但无作用，输出始终是 JSON")
    parser.add_argument("--format", choices=["json"], help="同 --json")
    parser.add_argument("--ai-help", action="store_true", help="给 AI 的使用说明")
    try:
        args = parser.parse_args(argv)
    except UsageError as exc:
        return _fail("E_VALIDATION", f"参数错误: {exc}", "用 --ai-help 看用法", exit_code=2)
    try:
        _emit(True, run(args))
        return 0
    except DesignError as exc:
        ordered = sorted(exc.problems, key=lambda p: (p.line is None, p.line or 0))
        problems = [p._asdict() for p in ordered]
        return _fail("E_VALIDATION", str(exc), "按 details.problems 逐条改 DESIGN.md 后重跑",
                     {"problems": problems})
    except MockupError as exc:
        return _fail("E_VALIDATION", str(exc), '在效果图 <head> 里加 <style id="design-tokens"></style> 后重跑')
    except StaleError as exc:
        return _fail("E_VERIFICATION_FAILED", str(exc), "不带 --check 重新生成，再提交产物",
                     {"files": exc.files})
    except UnicodeDecodeError as exc:
        return _fail("E_VALIDATION", f"DESIGN.md 不是 UTF-8: {exc}", "把 DESIGN.md 存成 UTF-8")
    except OSError as exc:
        code = _io_code(exc)
        return _fail(code, f"读写失败: {exc}", "检查路径和权限" if code != "E_NOT_FOUND" else "用 --design 指向项目根的 DESIGN.md")
    except Exception as exc:  # noqa: BLE001 —— 兜底，信封里报 E_INTERNAL
        return _fail("E_INTERNAL", f"未预期的错误: {exc!r}", "把 details 和 DESIGN.md 一起报给维护者")


if __name__ == "__main__":
    sys.exit(main())
