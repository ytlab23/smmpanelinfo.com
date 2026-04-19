# Static Page Split — Design

**Date:** 2026-04-19
**Goal:** Convert the single-file SPA at `index.html` into one static HTML file per page so each URL is independently crawlable and indexable.

## Problem

The site currently renders 19 pages from a single `index.html` using a `showPage()` JS function. URLs look clean (e.g. `/what-is-an-smm-panel`) only because of `history.pushState`. Any direct request to a non-root URL relies on a host-level fallback that serves `index.html`, so every page appears to search engines as the same HTML. SEO indexing per URL is unreliable.

## Goal state

Every page is served as its own real HTML file at the same URL it uses today:

- `/` → `index.html` (home)
- `/about` → `about/index.html`
- `/contact` → `contact/index.html`
- `/terms-and-disclaimer` → `terms-and-disclaimer/index.html`
- `/privacy-policy` → `privacy-policy/index.html`
- `/what-is-an-smm-panel` → `what-is-an-smm-panel/index.html`
- …plus 13 more topic slugs, one folder per `data-slug` value in the source.

No hash URLs. No client-side routing. Each file is fully self-contained HTML.

## Non-goals

- Changing visual design, copy, or CSS.
- Adding a new framework, bundler, or build tool beyond a Python script.
- Preserving SPA-style instant navigation. Internal links will be real page loads.

## Approach

1. Rename `index.html` → `_source.html`. This is the single template, edited by hand when content changes.
2. Add `_generate_pages.py` — a Python 3 stdlib script (no deps) that:
   - Reads `_source.html`.
   - Extracts the shared shell: `<head>` contents (minus the title/description tags which become per-page), the `<header>`, the `<footer>`.
   - Extracts each `<div id="X" class="page..." data-title data-description data-slug>…</div>` block by `<div>` balance scanning.
   - For each page, emits `<slug>/index.html` (or plain `index.html` for `data-slug=""`, i.e. home) containing:
     - Per-page `<title>`, `<meta name="description">`, `<link rel="canonical" href="https://smm-panel.website/<slug>">`, `og:title`, `og:description`, `og:url`, `twitter:card`.
     - Shared fonts/favicon/inline CSS.
     - `<header>`, the single page block (forced `class="page active"`), `<footer>`.
     - Trimmed `<script>` containing only `toggleFaq()`.
   - Rewrites every internal anchor: strips `onclick="showPage(...)"`, keeps the `href="/slug"`. Logo click becomes a real `<a href="/">`.
3. Run once. Commit the generated folders. Re-run whenever `_source.html` changes.

## Testing / verification

- After generation, each slug folder contains an `index.html` whose `<title>` matches the `data-title` in the source.
- Curl-style check: fetching `/about/index.html` returns HTML containing the About page's unique `<p class="page-num">Information</p>` and about-specific copy — not the home page's hero.
- No remaining `showPage(` calls in any generated file; no `href="#..."` anywhere.
- All 19 expected folders/files exist: `index.html` + 18 `<slug>/index.html`.

## Risks

- **Div-balance parser edge case**: if `_source.html` ever contains a non-matching `<div`/`</div>` inside a page block (e.g. commented out), the extractor could grab too little or too much. Mitigation: verify the generator's extracted block count (expect 19) and titles before writing.
- **Canonical drift**: if the production domain changes, regenerate. The canonical URL is a single constant in the generator.
