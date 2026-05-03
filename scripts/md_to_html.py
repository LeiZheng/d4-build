"""Render a Markdown file to a styled HTML file.

Usage: python scripts/md_to_html.py <input.md> <output.html>
"""

from __future__ import annotations

import sys
from pathlib import Path

import markdown

CSS = """
<style>
  :root {
    --bg: #f8fafc;
    --fg: #1e293b;
    --muted: #64748b;
    --accent: #be185d;
    --code-bg: #f1f5f9;
    --border: #e2e8f0;
  }
  body {
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", system-ui, sans-serif;
    line-height: 1.55;
    color: var(--fg);
    background: var(--bg);
    max-width: 980px;
    margin: 1.5em auto;
    padding: 0 1.5em 4em;
  }
  h1 { color: var(--accent); border-bottom: 2px solid var(--accent); padding-bottom: 0.2em; margin-top: 1.5em; }
  h2 { color: var(--accent); margin-top: 1.6em; border-bottom: 1px solid var(--border); padding-bottom: 0.15em; }
  h3 { margin-top: 1.4em; color: #475569; }
  h4 { margin-top: 1.2em; color: #334155; }
  table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 0.92em; }
  th, td { padding: 0.45em 0.7em; border: 1px solid var(--border); text-align: left; vertical-align: top; }
  th { background: #f1f5f9; font-weight: 600; }
  tr:nth-child(even) td { background: #fafbfc; }
  code { background: var(--code-bg); padding: 0.1em 0.4em; border-radius: 3px; font-family: "SF Mono", Menlo, monospace; font-size: 0.88em; }
  pre { background: var(--code-bg); padding: 0.9em 1.1em; border-radius: 5px; overflow-x: auto; }
  pre code { background: transparent; padding: 0; }
  blockquote { border-left: 4px solid var(--accent); padding: 0.4em 1em; color: var(--muted); margin: 1em 0; background: #fdf2f8; border-radius: 3px; }
  hr { border: 0; border-top: 1px solid var(--border); margin: 2em 0; }
  a { color: var(--accent); }
  sub { font-size: 0.78em; color: var(--muted); }
  ul li, ol li { margin: 0.2em 0; }
  table td:nth-child(2), table td:nth-child(1) { white-space: nowrap; }
  @media print {
    body { background: white; max-width: none; margin: 0; padding: 0.5in; }
    h1 { page-break-before: auto; }
    h2 { page-break-after: avoid; }
    table, pre, blockquote { page-break-inside: avoid; }
  }
</style>
"""


def main() -> None:
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    text = src.read_text()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    title = src.stem.replace("-", " ").title()
    dst.write_text(
        f'<!doctype html>\n<html lang="en"><head>\n'
        f'<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title}</title>\n{CSS}\n</head><body>\n{body}\n</body></html>\n'
    )
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
