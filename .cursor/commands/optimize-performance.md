# Optimize Performance (Scripts & Nodes)

## Overview

Systematically optimize the Instagram Parser project for **throughput**, **latency**, and **resource usage**. Focus on the main script (`instagram_accounts_topk.py`) and any related entrypoints. The stack is **async Python**, **HikerAPI** (HTTP), and **file I/O** (JSONL/CSV).

---

## Steps

### 1. **Audit current behavior**

- Read `instagram_accounts_topk.py` and identify:
  - Concurrency limits (e.g. `asyncio.Semaphore(10)`).
  - Per-request timeouts (HikerAPI/httpx defaults).
  - Order of operations: search → profile → reels per account; note where work is sequential vs parallel.
  - Any redundant API calls or repeated work.
  - How often files are opened/closed and how much is buffered in memory.

### 2. **Network & API usage**

- **Timeouts**: If the HikerAPI client accepts a `timeout` (e.g. `AsyncClient(token=..., timeout=30)`), set it explicitly so slow responses fail fast instead of hanging; consider a slightly higher value than default to reduce spurious timeouts while keeping runs bounded.
- **Concurrency**: Tune the semaphore (e.g. 10 → 15–20) only if you confirm HikerAPI allows it and the machine has headroom; avoid rate limits.
- **Retries**: For transient failures (e.g. `ReadTimeout`, 5xx), add a small retry with backoff (e.g. 1–2 retries, 1–2s delay) around `fbsearch_accounts_v3`, `user_by_id_v2`, and `user_clips` so occasional blips don’t wipe a full run.
- **Batching**: If the API supports batch endpoints (e.g. multiple user IDs in one request), prefer those over N single-id calls where applicable.

### 3. **Async and I/O**

- Ensure no blocking calls (e.g. synchronous file write or `requests.get`) run inside async functions; use `aiofiles` or run blocking I/O in an executor only if needed.
- Keep CSV/JSONL writes in a single pass at the end (as now) to avoid many small writes; if the result set is huge, consider streaming JSONL line-by-line while iterating, without loading everything into a list first.
- Avoid holding large raw API payloads in memory longer than necessary; normalize and discard what you don’t need.

### 4. **Algorithm and data flow**

- **Deduplication**: Multi-query dedupe by `pk` is already in place; ensure it runs once over the combined candidate list and doesn’t re-scan unnecessarily.
- **Early exit**: Skip fetching reels for accounts that fail profile fetch; avoid duplicate profile fetches for the same `pk`.
- **Order of work**: If useful, process accounts with higher follower count first so that partial results (e.g. interrupt) are more valuable; only if it doesn’t complicate the code.

### 5. **Implement and document**

- Apply only changes that are clearly beneficial and low-risk.
- Add brief comments or a short “Performance” subsection in README (e.g. timeout, semaphore, retries) so future maintainers know what was tuned.

---

## Performance checklist

- [ ] Timeouts set explicitly on HikerAPI/httpx client where supported.
- [ ] Retries with backoff for transient network/API errors (ReadTimeout, 5xx).
- [ ] Concurrency limit (semaphore) tuned and documented; no unnecessary serialization.
- [ ] No blocking I/O inside async paths; file writes batched or streamed as appropriate.
- [ ] No redundant API calls or repeated work per account.
- [ ] README or code comments updated with performance-related choices.
