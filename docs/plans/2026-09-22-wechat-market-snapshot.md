# WeChat Market Snapshot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a small, dependency-light fetcher that reads selected public WeChat articles, extracts the four market-information categories, and writes stable `latest.md`, `latest.json`, and dated archive snapshots for a scheduled GPT task.

**Architecture:** GitHub Actions runs a Python standard-library fetcher once daily after the expected article update. The fetcher parses the article metadata and `content_noencode`/`#js_content`, classifies each article into `zhihu_hot`, `submission_call`, `example_text`, or `trend_summary`, preserves title plus source-language intro text, and writes a human-readable Markdown file and a deduplicable JSON file. The first local verification uses the two user-provided article URLs; publishing to GitHub is a separate external step because repository visibility and credentials are not available in the current environment.

**Tech Stack:** Python 3.10+ standard library, GitHub Actions, JSON, Markdown, `urllib.request`, `html.parser`-compatible HTML extraction.

---

### Task 1: Define source and snapshot contract

**Files:**
- Create: `sources.json`
- Create: `README.md`
- Create: `docs/DAILY_TASK_PROMPT.md`

**Step 1: Write the source configuration and contract**

Include the two supplied public article URLs and document that the example article is categorized as `example_text` unless a future article contains an explicit submission request.

**Step 2: Verify the contract**

Run: `py -m json.tool sources.json`

Expected: valid JSON with two source URLs.

### Task 2: Implement the parser and snapshot writer

**Files:**
- Create: `src/fetch_wechat.py`

**Step 1: Implement fetch and metadata extraction**

Use a browser-like User-Agent, bounded timeout, retries, and the page's `og:title`, profile name, and `create_time` metadata.

**Step 2: Implement content decoding and item extraction**

Decode the escaped `content_noencode` payload, fall back to `#js_content`, split `TOP N` entries, preserve the source-language intro, and add heuristic tags without claiming they are editorial truth.

**Step 3: Implement four fixed section types**

Always emit the four section types. Populate only the type supported by the current article; keep absent types with empty item arrays so downstream prompts have a stable schema.

**Step 4: Implement Markdown and JSON output**

Write `data/latest.md`, `data/latest.json`, and `data/archive/YYYY-MM-DD.json`. Do not overwrite historical archive files with a different date.

### Task 3: Add deterministic parser tests

**Files:**
- Create: `tests/test_parser.py`

**Step 1: Test the `TOP N` parser**

Verify rank, title, intro, and tags from a small HTML fixture.

**Step 2: Test section classification**

Verify a `知乎风短篇小说热榜` title maps to `zhihu_hot` and `编辑收稿例文榜` maps to `example_text`.

**Step 3: Run the tests**

Run: `py -m unittest discover -s tests -v`

Expected: all tests pass without network access.

### Task 4: Add the scheduled workflow

**Files:**
- Create: `.github/workflows/daily.yml`

**Step 1: Schedule the fetch**

Run daily at 10:00 Asia/Shanghai, with a manual dispatch option.

**Step 2: Commit only changed snapshots**

Use the repository's `GITHUB_TOKEN` to commit updated latest files and a dated archive.

**Step 3: Document operational limits**

Note that scheduled workflows can be delayed and that a public repository can expose its snapshot content.

### Task 5: Run a real two-source verification

**Files:**
- Generate: `data/latest.md`
- Generate: `data/latest.json`
- Generate: `data/archive/2026-09-22.json`

**Step 1: Fetch both supplied URLs**

Run the parser against the live pages.

**Step 2: Inspect the generated snapshot**

Verify that the first source contains `zhihu_hot`, the second contains `example_text`, titles and intros are non-empty, and all four section keys exist.

**Step 3: Report the remaining deployment blocker**

Do not create or publish a GitHub repository without a user-provided repository or explicit visibility choice.
