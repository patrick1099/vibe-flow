"""skills/vibe-apps/scripts/design_theme.py 的测试：front matter 子集解析、支持范围校验、三种产物、CLI 契约。

运行：py -3 -m unittest discover -s tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "vibe-apps" / "scripts" / "design_theme.py"
sys.path.insert(0, str(SCRIPT.parent))
import design_theme as dt  # noqa: E402

TTK_COLORS = """\
  primary: "#2563eb"
  secondary: "#64748b"
  success: "#16a34a"
  info: "#0891b2"
  warning: "#d97706"
  error: "#dc2626"
  base-100: "#f0f0f0"
  base-content: "#1a1a1a"
  base-200: "#e5e5e5"
  neutral: "#404040"
  selection: "#bfdbfe"
  selection-content: "#1a1a1a"
  border: "#c0c0c0"
  input: "#ffffff"
  input-content: "#1a1a1a"
  active: "#dbeafe"
"""

VALID = f"""---
version: alpha
name: Probe
description: |
  多行说明：这里写什么都不解析
  - 连列表样子的行也不管
omitted:
  - section: components
    reason: 原生项目不写
colors:
{TTK_COLORS}  accent: '#F0A'   # 三位 hex，单引号
typography:
  body:
    fontFamily: Microsoft YaHei UI
    fontSize: 12px
  title:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 16px
    fontWeight: "700"
rounded:
  sm: 2px
spacing:
  sm: 4px
  md: 8px
---

# Probe

## Overview
正文改了不算设计变了。
"""


def with_section(extra, base=VALID):
    """在 front matter 末尾（结束的 --- 之前）追加几行。"""
    head, sep, tail = base.rpartition("\n---\n")
    return head + "\n" + extra.rstrip("\n") + sep + tail


def problems(text, target="ttk"):
    try:
        dt.generate(text, target)
    except dt.DesignError as exc:
        return exc.problems
    return []


def messages(text, target="ttk"):
    return " | ".join(f"{p.where}: {p.message}" for p in problems(text, target))


class ParseTest(unittest.TestCase):
    def test_valid_file_generates_theme_and_css(self):
        rel, theme, css = dt.generate(VALID, "ttk")
        self.assertEqual(rel, "design_tokens.py")
        self.assertIn("TTK_COLORS", theme)
        self.assertTrue(css.splitlines()[1] == ":root {")

    def test_scalars(self):
        self.assertEqual(dt.parse_scalar('"a \\"b\\" c"  # note'), ('a "b" c', None))
        self.assertEqual(dt.parse_scalar("'it''s'"), ("it's", None))
        self.assertEqual(dt.parse_scalar("12px # x"), ("12px", None))
        self.assertEqual(dt.parse_scalar("400"), (400, None))
        self.assertEqual(dt.parse_scalar("1.5"), (1.5, None))
        self.assertEqual(dt.parse_scalar("010")[0], "010")
        for bad in ("[a, b]", "{a: 1}", "&anchor x", "*ref", "| ", "yes", "null", '"open', "a: b"):
            self.assertIsNotNone(dt.parse_scalar(bad)[1], bad)

    def test_unquoted_hex_is_comment_and_reported(self):
        text = VALID.replace('primary: "#2563eb"', "primary: #2563eb")
        self.assertIn("加引号", messages(text))

    def test_comment_after_section_key(self):
        text = VALID.replace("rounded:\n", "rounded: # 圆角\n")
        self.assertEqual(problems(text), [])

    def test_syntax_outside_subset(self):
        cases = {
            "colors:\n\tx: \"#fff\"": "tab",
            "shadow: [a]": "YAML 写法",
            "colors:\n  primary: \"#111111\"": "重复",
            "shadow:\n  a: 1px\n   b: 2px": "缩进不一致",
            "\"quoted\": 1": "看不懂",
            "- item": "omitted",
        }
        for extra, needle in cases.items():
            self.assertIn(needle, messages(with_section(extra)), extra)

    def test_all_problems_reported_with_lines(self):
        text = with_section('foo: 1\nshadow:\n  sm: 2px')
        text = text.replace("sm: 4px", "sm: 4").replace("sm: 2px\nspacing", "sm: 1rem\nspacing")
        found = problems(text)
        wheres = {p.where for p in found}
        self.assertTrue({"foo", "shadow", "spacing.sm", "rounded.sm"} <= wheres, wheres)
        lines = VALID.split("\n")
        self.assertEqual(next(p.line for p in found if p.where == "rounded.sm"),
                         lines.index("rounded:") + 2)

    def test_crlf_gives_same_output(self):
        self.assertEqual(dt.generate(VALID, "slint"), dt.generate(VALID.replace("\n", "\r\n"), "slint"))

    def test_body_prose_does_not_change_digest(self):
        self.assertEqual(dt.generate(VALID, "ttk"), dt.generate(VALID + "\n多一段正文\n", "ttk"))

    def test_missing_front_matter(self):
        self.assertIn("front matter", messages("# 只有正文\n"))
        self.assertIn("结束", messages("---\ncolors:\n"))


class SupportRangeTest(unittest.TestCase):
    def test_values_outside_v1(self):
        cases = [
            ('selection: "#bfdbfe"', 'selection: "rgba(37, 99, 235, 0.3)"', "hex"),
            ("md: 8px", "md: 8", "无单位"),
            ("sm: 2px", "sm: 0.5em", "em / rem"),
            ("fontSize: 12px", "fontSize: 12", "fontSize 要写单位"),
            ("fontSize: 12px", "fontSize: 12px\n    lineHeight: 1.5", "lineHeight"),
            ("fontSize: 12px", "fontSize: 12px\n    letterSpacing: 1px", "letterSpacing"),
            ("fontSize: 12px", "fontSize: 12px\n    textCase: upper", "不认识的 typography 属性"),
            ("fontFamily: Microsoft YaHei UI", "fontFamily: Segoe UI, sans-serif", "一个字体族"),
            ('fontWeight: "700"', "fontWeight: 650", "整百"),
        ]
        for old, new, needle in cases:
            self.assertIn(old, VALID)
            self.assertIn(needle, messages(VALID.replace(old, new, 1), "slint"), new)

    def test_components_rejected(self):
        self.assertIn("components 段 v1 不支持", messages(with_section('components:\n  button:\n    height: 24px')))

    def test_missing_font_size(self):
        self.assertIn("缺 fontSize", messages(VALID.replace("    fontSize: 16px\n", "")))

    def test_ttk_needs_all_slots(self):
        text = VALID.replace('  active: "#dbeafe"\n', "").replace('  border: "#c0c0c0"\n', "")
        msg = messages(text)
        self.assertIn("还缺：border active", msg)
        self.assertEqual(problems(text, "slint"), [])

    def test_ttk_only_limits(self):
        cases = [('fontWeight: "700"', "fontWeight: 500"), ("fontSize: 12px", "fontSize: 12.5px"),
                 ('active: "#dbeafe"', 'active: "#dbeafe80"'), ("md: 8px", "md: 8.5px")]
        for old, new in cases:
            text = VALID.replace(old, new, 1)
            self.assertNotEqual(problems(text, "ttk"), [], new)
            self.assertEqual(problems(text, "slint"), [], new)

    def test_slint_identifiers(self):
        text = with_section("", VALID.replace('  accent:', '  2xl: "#000000"\n  accent:'))
        self.assertIn("合法的 Slint 标识符", messages(text, "slint"))
        text = VALID.replace('  accent:', '  foo_bar: "#000000"\n  foo-bar: "#111111"\n  accent:')
        self.assertIn("重名", messages(text, "slint"))
        text = VALID.replace('  accent:', '  body-size: "#000000"\n  accent:')
        self.assertIn("重名", messages(text, "slint"))


class RenderTest(unittest.TestCase):
    def render(self, target):
        _, theme, css = dt.generate(VALID, target)
        return {"theme": theme, "css": css}

    def test_ttk_module_is_plain_data(self):
        ns = {}
        exec(self.render("ttk")["theme"], ns)
        self.assertEqual(set(ns["TTK_COLORS"]), set(dt.TTK_SLOTS))
        self.assertEqual(ns["TTK_COLORS"]["danger"], "#dc2626")
        self.assertEqual(ns["TTK_COLORS"]["bg"], "#f0f0f0")
        self.assertEqual(ns["COLORS"]["accent"], "#ff00aa")
        self.assertEqual(ns["FONTS"]["body"], ("Microsoft YaHei UI", -12, "normal"))
        self.assertEqual(ns["FONTS"]["title"], ("Microsoft YaHei UI", -16, "bold"))
        self.assertEqual(ns["SPACING"], {"sm": 4, "md": 8})
        self.assertEqual(ns["ROUNDED"], {"sm": 2})

    def test_slint(self):
        theme = self.render("slint")["theme"]
        self.assertIn("export global Theme {", theme)
        for line in ("out property <color> base-100: #f0f0f0;", "out property <length> spacing-md: 8px;",
                     "out property <length> rounded-sm: 2px;", 'out property <string> body-family: "Microsoft YaHei UI";',
                     "out property <length> title-size: 16px;", "out property <int> title-weight: 700;"):
            self.assertIn(line, theme)

    def test_css(self):
        css = self.render("ttk")["css"]
        for line in ("--color-base-100: #f0f0f0;", "--spacing-md: 8px;", "--rounded-sm: 2px;",
                     '--font-body-family: "Microsoft YaHei UI";', "--font-body-size: 12px;", "--font-body-weight: 400;"):
            self.assertIn(line, css)

    def test_string_escaping(self):
        text = VALID.replace("fontFamily: Microsoft YaHei UI", 'fontFamily: "A\\\\B \\"Q\\""')
        theme = dt.generate(text, "slint")[1]
        self.assertIn('body-family: "A\\\\B \\"Q\\"";', theme)


class MockupTest(unittest.TestCase):
    HTML = '<html><head>\n<style id="design-tokens"></style>\n<style>body{}</style>\n</head><body>手写</body></html>\n'

    def test_inject_replaces_only_the_block(self):
        css = dt.generate(VALID, "ttk")[2]
        out = dt.inject_tokens(self.HTML, css)
        self.assertIn("--color-primary: #2563eb;", out)
        self.assertTrue(out.endswith('</style>\n<style>body{}</style>\n</head><body>手写</body></html>\n'))
        self.assertEqual(dt.inject_tokens(out, css), out)

    def test_inject_keeps_crlf(self):
        out = dt.inject_tokens(self.HTML.replace("\n", "\r\n"), dt.generate(VALID, "ttk")[2])
        self.assertNotIn("\n", out.replace("\r\n", ""))

    def test_block_must_exist_once(self):
        for html in ("<html></html>", self.HTML + '<style id="design-tokens"></style>'):
            with self.assertRaises(dt.MockupError):
                dt.inject_tokens(html, "x")


class RegistryTest(unittest.TestCase):
    def test_fake_target_reaches_cli_and_generate(self):
        fake = {"out": "fake.txt", "check": lambda m: [], "render": lambda m, d: "fake\n"}
        dt.TARGETS["fake"] = fake
        try:
            self.assertEqual(dt.generate(VALID, "fake")[:2], ("fake.txt", "fake\n"))
            with tempfile.TemporaryDirectory() as d:
                Path(d, "DESIGN.md").write_text(VALID, encoding="utf-8")
                rc = dt.main(["fake", "--design", str(Path(d, "DESIGN.md"))])
                self.assertEqual(rc, 0)
                self.assertEqual(Path(d, "fake.txt").read_text(encoding="utf-8"), "fake\n")
        finally:
            del dt.TARGETS["fake"]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.design = self.root / "DESIGN.md"
        self.design.write_text(VALID, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")
        stream = proc.stdout if proc.returncode == 0 else proc.stderr
        envelope = json.loads(stream) if stream.strip().startswith("{") else None
        return proc, envelope

    def add_mockup(self, html=MockupTest.HTML):
        mockup = self.root / "docs" / "mockup" / "index.html"
        mockup.parent.mkdir(parents=True)
        mockup.write_text(html, encoding="utf-8", newline="")
        return mockup

    def statuses(self, env):
        return [f["status"] for f in env["data"]["files"]]

    def test_generate_then_check(self):
        mockup = self.add_mockup()
        proc, env = self.cli("slint", "--design", str(self.design))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(env), ["created", "updated"])
        self.assertTrue((self.root / "ui" / "theme.slint").is_file())
        self.assertIn("--spacing-md: 8px;", mockup.read_text(encoding="utf-8"))
        proc, env = self.cli("slint", "--design", str(self.design), "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(env), ["unchanged", "unchanged"])

    def test_missing_mockup_is_skipped_and_reported(self):
        proc, env = self.cli("ttk", "--design", str(self.design))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(env), ["created", "skipped"])
        proc, env = self.cli("ttk", "--design", str(self.design), "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_mockup_without_block_fails_untouched(self):
        mockup = self.add_mockup("<html><head></head></html>\n")
        proc, env = self.cli("ttk", "--design", str(self.design))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(env["error"]["code"], "E_VALIDATION")
        self.assertIn("design-tokens", env["error"]["message"])
        self.assertEqual(mockup.read_text(encoding="utf-8"), "<html><head></head></html>\n")

    def test_check_reports_stale_without_writing(self):
        mockup = self.add_mockup()
        self.cli("ttk", "--design", str(self.design))
        theme = self.root / "design_tokens.py"
        before = theme.read_text(encoding="utf-8"), mockup.read_text(encoding="utf-8")
        self.design.write_text(VALID.replace("#2563eb", "#1d4ed8"), encoding="utf-8")
        proc, env = self.cli("ttk", "--design", str(self.design), "--check")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(env["error"]["code"], "E_VERIFICATION_FAILED")
        self.assertEqual([f["status"] for f in env["error"]["details"]["files"]], ["updated", "updated"])
        self.assertEqual((theme.read_text(encoding="utf-8"), mockup.read_text(encoding="utf-8")), before)

    def test_crlf_output_on_disk_counts_as_unchanged(self):
        self.cli("ttk", "--design", str(self.design))
        theme = self.root / "design_tokens.py"
        theme.write_bytes(theme.read_bytes().replace(b"\n", b"\r\n"))
        proc, env = self.cli("ttk", "--design", str(self.design), "--check")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_dry_run_writes_nothing(self):
        proc, env = self.cli("ttk", "--design", str(self.design), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(env["data"]["dry_run"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["DESIGN.md"])

    def test_out_and_mockup_overrides(self):
        out, mockup = self.root / "pkg" / "tokens.py", self.root / "m.html"
        mockup.write_text(MockupTest.HTML, encoding="utf-8")
        proc, env = self.cli("ttk", "--design", str(self.design), "--out", str(out), "--mockup", str(mockup))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(env), ["created", "updated"])
        self.assertTrue(out.is_file())

    def test_validation_failure_envelope(self):
        self.design.write_text(VALID.replace("md: 8px", "md: 8"), encoding="utf-8")
        proc, env = self.cli("ttk", "--design", str(self.design))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(env["error"]["code"], "E_VALIDATION")
        self.assertEqual(env["error"]["details"]["problems"][0]["where"], "spacing.md")
        self.assertFalse((self.root / "design_tokens.py").exists())

    def test_missing_design(self):
        proc, env = self.cli("ttk", "--design", str(self.root / "nope.md"))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(env["error"]["code"], "E_NOT_FOUND")

    def test_usage_error(self):
        proc, env = self.cli("qt")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(env["error"]["code"], "E_VALIDATION")

    def test_ai_help_is_eager_and_respects_double_dash(self):
        proc, _ = self.cli("--ai-help")
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(proc.stdout.startswith("---\nname: design_theme"))
        proc, _ = self.cli("--", "--ai-help")
        self.assertEqual(proc.returncode, 2)

    def test_json_flags_accepted(self):
        proc, _ = self.cli("ttk", "--design", str(self.design), "--json", "--format", "json", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
