# Investigate Error Logs & Fix Issues

## Overview

Systematically investigate `error_log.jsonl` in this project, identify root causes, produce a **to-do list with explanations and concrete fix arguments**, then **implement the fixes** in code (and docs if needed). Error log format: one JSON object per line with `ts`, `context`, `error_type`, `error_message`, optional `traceback`, and context-specific fields (e.g. `query`, `user_id`, `pk`, `username`).

---

## Steps

### 1. **Load and parse the error log**

- Read `error_log.jsonl` from the project root (ignore missing file or empty file with a clear note).
- Parse each line as JSON; skip malformed lines and note the count.
- Build a list of records with at least: `context`, `error_type`, `error_message`, and any IDs (e.g. `user_id`, `pk`, `query`).

### 2. **Categorize and summarize**

- Group entries by:
  - **context** (e.g. `fbsearch_accounts_v3`, `user_by_id_v2`, `user_clips`).
  - **error_type** (e.g. `KeyError`, `ReadTimeout`, `InsufficientFunds`).
- For each group, summarize:
  - Count.
  - Typical `error_message` and where in the stack it occurs (our code vs dependency, e.g. `hikerapi`/`httpx`).
  - Likely root cause (API response shape change, timeout, rate limit, bug in our code, etc.).

### 3. **Produce a to-do list**

Write a **numbered to-do list** in the chat with:

- **Short title** (e.g. “Handle missing `response` in user_clips”).
- **Explanation**: why this happens (root cause) and impact (e.g. “reels not fetched for some users”).
- **Fix argument**: what to do (e.g. “wrap `user_clips` in try/except; on KeyError or missing `response`, log and return []”; or “increase client timeout and add retries for ReadTimeout”).
- **Where**: file and function/section (e.g. `instagram_accounts_topk.py`, `fetch_reels`).

Keep the list actionable: one item per logical fix.

### 4. **Apply fixes**

- For each to-do item:
  - Implement the change in the codebase (or docs).
  - Prefer defensive handling (e.g. tolerate unexpected API response shapes, retries for transient errors) without changing behavior for successful cases.
- If a fix is in a **third-party** package (e.g. `hikerapi`), document the finding and add a workaround in **our** code (e.g. catch the exception, fallback, or retry) plus a comment or README note (e.g. “Known issue: hikerapi …; we do X until upstream fix”).

### 5. **Optional: error log hygiene**

- If the project has a convention (e.g. rotate or truncate `error_log.jsonl` after investigation), add a brief note in README or leave as-is; no need to implement rotation unless the user asks.

---

## Investigation checklist

- [ ] `error_log.jsonl` read and parsed; counts and groups reported.
- [ ] Root causes explained per context/error_type.
- [ ] To-do list with title, explanation, fix argument, and location.
- [ ] Fixes implemented in code (and docs where relevant).
- [ ] No regressions: successful flows unchanged; only error handling and resilience improved.
