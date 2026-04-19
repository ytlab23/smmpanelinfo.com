#!/usr/bin/env python3
"""Split _source.html into one static HTML file per page.

Each <div id="..." class="page ..." data-title data-description data-slug>
becomes its own `/<slug>/index.html` (or root `index.html` for the home page).
Re-run whenever _source.html changes.
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "_source.html"
CANONICAL_BASE = "https://smm-panel.website"


def read_source() -> str:
    if not SOURCE.exists():
        sys.exit(f"missing source file: {SOURCE}")
    return SOURCE.read_text(encoding="utf-8")


def split_head(source: str) -> tuple[str, str]:
    m = re.search(r"<head>(.*?)</head>", source, re.DOTALL | re.IGNORECASE)
    if not m:
        sys.exit("could not find <head> in source")
    head_inner = m.group(1)
    # drop the existing <title> and <meta name="description"> - they become per-page
    head_inner = re.sub(r"<title>.*?</title>\s*", "", head_inner, flags=re.DOTALL | re.IGNORECASE)
    head_inner = re.sub(
        r'<meta\s+name="description"[^>]*>\s*', "", head_inner, flags=re.IGNORECASE
    )
    return head_inner.strip(), source


def extract_block(source: str, start_tag_start: int) -> tuple[str, int]:
    """Return (full block text including closing </div>, index after it) by balancing <div>/</div>."""
    i = start_tag_start
    depth = 0
    n = len(source)
    open_re = re.compile(r"<div\b", re.IGNORECASE)
    close_re = re.compile(r"</div>", re.IGNORECASE)
    while i < n:
        o = open_re.search(source, i)
        c = close_re.search(source, i)
        if c is None:
            sys.exit("unbalanced <div> in source")
        if o is not None and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
            if depth == 0:
                return source[start_tag_start:i], i
    sys.exit("unbalanced <div> in source")


PAGE_START_RE = re.compile(
    r'<div\s+id="([^"]+)"\s+class="page[^"]*"\s+'
    r'data-title="([^"]*)"\s+'
    r'data-description="([^"]*)"\s+'
    r'data-slug="([^"]*)">',
    re.IGNORECASE,
)


def find_pages(source: str) -> list[dict]:
    pages: list[dict] = []
    for m in PAGE_START_RE.finditer(source):
        block, _ = extract_block(source, m.start())
        pages.append(
            {
                "id": m.group(1),
                "title": html.unescape(m.group(2)),
                "description": html.unescape(m.group(3)),
                "slug": m.group(4),
                "block": block,
            }
        )
    return pages


def extract_header(source: str) -> str:
    m = re.search(r"<header\b[^>]*>.*?</header>", source, re.DOTALL | re.IGNORECASE)
    if not m:
        sys.exit("could not find <header>")
    return m.group(0)


def extract_footer(source: str) -> str:
    m = re.search(r"<footer\b[^>]*>.*?</footer>", source, re.DOTALL | re.IGNORECASE)
    if not m:
        sys.exit("could not find <footer>")
    return m.group(0)


LINK_RE = re.compile(r'(<a[^>]*?)\s+onclick="showPage\([^)]*\)"', re.IGNORECASE)
LOGO_RE = re.compile(
    r'<div class="logo-wrap"\s+onclick="showPage\(\'home\'\)">(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
CARD_RE = re.compile(
    r'^(\s*)<div class="card" onclick="showPage\(\'([^\']+)\'\)">(.*)</div>\s*$',
    re.MULTILINE | re.IGNORECASE,
)


def rewrite_links(fragment: str, id_to_slug: dict[str, str]) -> str:
    fragment = LINK_RE.sub(r"\1", fragment)
    fragment = LOGO_RE.sub(
        r'<a class="logo-wrap" href="/" style="text-decoration:none;color:inherit;">\1</a>',
        fragment,
    )

    def card_sub(m: re.Match) -> str:
        indent = m.group(1)
        page_id = m.group(2)
        inner = m.group(3)
        slug = id_to_slug.get(page_id, "")
        href = f"/{slug}" if slug else "/"
        return (
            f'{indent}<a class="card" href="{href}" '
            f'style="text-decoration:none;color:inherit;">{inner}</a>'
        )

    fragment = CARD_RE.sub(card_sub, fragment)
    return fragment


def activate_page_block(block: str) -> str:
    # Force the single page on the output to be active (visible).
    return re.sub(
        r'(<div\s+id="[^"]+"\s+class="page)[^"]*(")',
        r"\1 active\2",
        block,
        count=1,
        flags=re.IGNORECASE,
    )


SCRIPT = """<script>
  function toggleFaq(el) {
    const answer = el.nextElementSibling;
    const isOpen = answer.classList.contains('open');
    el.closest('.faq').querySelectorAll('.faq-q').forEach(q => q.classList.remove('open'));
    el.closest('.faq').querySelectorAll('.faq-a').forEach(a => a.classList.remove('open'));
    if (!isOpen) {
      el.classList.add('open');
      answer.classList.add('open');
    }
  }
</script>"""


def build_head(page: dict, shared_head_inner: str) -> str:
    title = page["title"]
    description = page["description"]
    slug = page["slug"]
    canonical = f"{CANONICAL_BASE}/{slug}" if slug else f"{CANONICAL_BASE}/"
    esc_title = html.escape(title, quote=True)
    esc_desc = html.escape(description, quote=True)
    esc_canonical = html.escape(canonical, quote=True)
    meta_tags = (
        f"<title>{esc_title}</title>\n"
        f'<meta name="description" content="{esc_desc}">\n'
        f'<link rel="canonical" href="{esc_canonical}">\n'
        f'<meta name="application-name" content="SMM Panel">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:site_name" content="SMM Panel">\n'
        f'<meta property="og:title" content="{esc_title}">\n'
        f'<meta property="og:description" content="{esc_desc}">\n'
        f'<meta property="og:url" content="{esc_canonical}">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{esc_title}">\n'
        f'<meta name="twitter:description" content="{esc_desc}">\n'
    )
    return f"<head>\n{meta_tags}{shared_head_inner}\n</head>"


def build_html(
    page: dict,
    shared_head_inner: str,
    header: str,
    footer: str,
    id_to_slug: dict[str, str],
) -> str:
    block = activate_page_block(page["block"])
    header_out = rewrite_links(header, id_to_slug)
    block_out = rewrite_links(block, id_to_slug)
    footer_out = rewrite_links(footer, id_to_slug)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        f"{build_head(page, shared_head_inner)}\n"
        "<body>\n\n"
        f"{header_out}\n\n"
        f"{block_out}\n\n"
        f"{footer_out}\n\n"
        f"{SCRIPT}\n"
        "</body>\n"
        "</html>\n"
    )


def output_path(slug: str) -> Path:
    if slug == "":
        return ROOT / "index.html"
    return ROOT / slug / "index.html"


def clean_previous_outputs(slugs: list[str]) -> None:
    for slug in slugs:
        if not slug:
            continue
        d = ROOT / slug
        if d.is_dir():
            shutil.rmtree(d)


def main() -> None:
    source = read_source()
    shared_head_inner, _ = split_head(source)
    header = extract_header(source)
    footer = extract_footer(source)
    pages = find_pages(source)

    if not pages:
        sys.exit("no pages found in source")

    slugs = [p["slug"] for p in pages]
    if len(slugs) != len(set(slugs)):
        sys.exit(f"duplicate slugs detected: {slugs}")

    id_to_slug = {p["id"]: p["slug"] for p in pages}

    print(f"found {len(pages)} pages:")
    for p in pages:
        print(f"  - {p['id']:>6}  slug={p['slug']!r:40}  title={p['title']!r}")

    clean_previous_outputs(slugs)

    for p in pages:
        out = output_path(p["slug"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            build_html(p, shared_head_inner, header, footer, id_to_slug),
            encoding="utf-8",
        )
        print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
