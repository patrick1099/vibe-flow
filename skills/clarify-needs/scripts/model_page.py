"""把一张 D2 运行模型图渲染成可在浏览器里看的单文件 HTML 页面。

用法:
    py -3 model_page.py <图.d2> --title 标题 [--anchor 真需求] [--layer run|build]
                        [--q "位置::要问的"]... [--out 页面.html] [--open]

.d2 里只写框和线,样式用下面 PRELUDE 里的 class:
    step 已确认的步骤 / ask 判断(菱形) / guess 我猜的待拍板 / done 最后拿到的
    store 文件或数据 / 连线 class: maybe 表示猜的路径

退出码: 0 成功;1 D2 编译失败;2 用法错或本机没装 d2(调用方应退回 ASCII 图)。
"""

import argparse
import base64
import html
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

PRELUDE = """
vars: {
  d2-config: {
    theme-id: 0
    layout-engine: elk
  }
}
classes: {
  step: {
    style: {border-radius: 10; fill: "#EEF4FF"; stroke: "#3B6FD8"; font-color: "#1F2A44"; shadow: true}
  }
  ask: {
    shape: diamond
    style: {fill: "#FFFFFF"; stroke: "#3B6FD8"; font-color: "#1F2A44"}
  }
  guess: {
    style: {border-radius: 10; fill: "#FFF6E0"; stroke: "#E0A100"; stroke-dash: 4; font-color: "#7A5200"}
  }
  done: {
    style: {border-radius: 10; fill: "#E8F7EE"; stroke: "#2E9E5B"; font-color: "#1B4D2F"}
  }
  store: {
    shape: cylinder
    style: {fill: "#F3F0FF"; stroke: "#7B61C9"; font-color: "#33265E"}
  }
  maybe: {
    style: {stroke: "#E0A100"; stroke-dash: 4}
  }
}
"""

LAYERS = {
    "run": "它跑起来是什么样 · 你的视角，不含实现",
    "build": "我打算怎么搭 · 模块与数据怎么流",
}

CSS = """
:root { color-scheme: light;
  --bg: #f6f7fb; --card: #fff; --ink: #1f2a44; --muted: #6b7489; --line: #e3e7ef;
  --blue: #3b6fd8; --blue-bg: #eef4ff; --amber: #e0a100; --amber-bg: #fff6e0;
  --green: #2e9e5b; --green-bg: #e8f7ee; --violet: #7b61c9; --violet-bg: #f3f0ff; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.6 "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif; }
main { max-width: 1200px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 22px; margin: 0 0 4px; }
.sub { margin: 0; color: var(--muted); }
.anchor { margin: 20px 0; padding: 14px 18px; background: var(--card); border-left: 4px solid var(--blue);
  border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
.anchor b { color: var(--blue); margin-right: 6px; }
.card { background: var(--card); border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: var(--muted); margin-bottom: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.sw { width: 18px; height: 12px; border-radius: 3px; border: 2px solid; display: inline-block; }
.sw.step { background: var(--blue-bg); border-color: var(--blue); }
.sw.guess { background: var(--amber-bg); border-color: var(--amber); border-style: dashed; }
.sw.done { background: var(--green-bg); border-color: var(--green); }
.sw.store { background: var(--violet-bg); border-color: var(--violet); border-radius: 6px / 4px; }
.diagram { overflow-x: auto; }
.diagram img { width: 100%; height: auto; min-width: 640px; display: block; }
h2 { font-size: 17px; margin: 28px 0 10px; }
ol.qs { margin: 0; padding: 0; list-style: none; counter-reset: q; }
ol.qs li { counter-increment: q; display: flex; gap: 12px; align-items: baseline; padding: 12px 16px;
  background: var(--amber-bg); border: 1px dashed var(--amber); border-radius: 8px; margin-bottom: 8px; }
ol.qs li::before { content: counter(q); font-weight: 700; color: var(--amber); }
.q-where { font-weight: 600; min-width: 9em; }
.q-ask { color: #7a5200; }
.clear { padding: 12px 16px; background: var(--green-bg); border: 1px solid var(--green); border-radius: 8px; color: #1b4d2f; }
footer { margin-top: 32px; font-size: 12px; color: var(--muted); }
@media (max-width: 640px) { ol.qs li { flex-direction: column; gap: 2px; } }
"""


def fail(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def render_svg(d2_path, sketch):
    exe = shutil.which("d2")
    if not exe:
        fail(2, "本机没有 d2(https://d2lang.com),请退回 ASCII 图")
    # 样式段放末尾,d2 报错的行号才和用户的 .d2 对得上
    source = d2_path.read_text(encoding="utf-8") + "\n" + PRELUDE
    cmd = [exe, "--pad", "24"] + (["--sketch"] if sketch else []) + ["-", "-"]
    r = subprocess.run(cmd, input=source.encode("utf-8"), capture_output=True)
    if r.returncode != 0 or not r.stdout.lstrip().startswith(b"<"):
        fail(1, "d2 编译失败:\n" + r.stderr.decode("utf-8", "replace"))
    return r.stdout


def parse_questions(raw):
    out = []
    for item in raw:
        where, sep, ask = item.partition("::")
        out.append((where.strip(), ask.strip()) if sep else ("", where.strip()))
    return out


def build_page(title, layer, anchor, svg, questions, source_name):
    e = html.escape
    img = base64.b64encode(svg).decode()
    anchor_html = f'<div class="anchor"><b>真需求</b>{e(anchor)}</div>' if anchor else ""
    if questions:
        items = "\n".join(
            f'<li><span class="q-where">{e(w)}</span><span class="q-ask">{e(a)}</span></li>'
            for w, a in questions
        )
        qs = f'<h2>图上这 {len(questions)} 处要你定</h2>\n<ol class="qs">\n{items}\n</ol>'
    else:
        qs = '<h2>待定项</h2>\n<div class="clear">没有待定项，图上都已确认。</div>'
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>{e(title)}</h1>
<p class="sub">{e(LAYERS[layer])}</p>
{anchor_html}
<div class="card">
<div class="legend">
<span><i class="sw step"></i>已确认</span>
<span><i class="sw guess"></i>我猜的，待你拍板</span>
<span><i class="sw done"></i>你最后拿到的</span>
<span><i class="sw store"></i>文件 / 数据</span>
</div>
<div class="diagram"><img alt="{e(title)}" src="data:image/svg+xml;base64,{img}"></div>
</div>
{qs}
<footer>源文件 {e(source_name)} · 生成于 {stamp}</footer>
</main>
</body>
</html>
"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="D2 运行模型图 → 单文件 HTML 页面")
    p.add_argument("d2", type=Path)
    p.add_argument("--title", required=True)
    p.add_argument("--anchor", default="")
    p.add_argument("--layer", choices=list(LAYERS), default="run")
    p.add_argument("--q", action="append", default=[], metavar="位置::要问的")
    p.add_argument("--out", type=Path)
    p.add_argument("--sketch", action="store_true", help="手绘风(默认平整)")
    p.add_argument("--open", action="store_true", help="生成后用默认浏览器打开")
    a = p.parse_args()

    if not a.d2.is_file():
        fail(2, f"找不到 {a.d2}")
    out = a.out or a.d2.with_suffix(".html")
    svg = render_svg(a.d2, a.sketch)
    page = build_page(a.title, a.layer, a.anchor, svg, parse_questions(a.q), a.d2.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(out.resolve())
    if a.open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
