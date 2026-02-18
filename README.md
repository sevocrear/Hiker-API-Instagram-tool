## Instagram HikerAPI Top‑K Accounts && Reels Tool

CLI tool that uses **HikerAPI** to:

- **search Instagram accounts** by keyword (similar to in‑app search)
- **fetch profile info** for the most relevant accounts
- **fetch recent reels** for each account
- **rank Top‑K reels** by views and date
- **export results** to JSONL and CSV for further analysis

Under the hood it uses only **non‑deprecated HikerAPI endpoints** from the official docs  
([HikerAPI Python docs](https://hiker-doc.readthedocs.io/en/latest/python.html)):

- `fbsearch_accounts_v3` – account search
- `user_by_id_v2` – full profile by id
- `user_clips` – recent reels (clips) for a user

---

### Requirements

- Python **3.9+**
- A valid **HikerAPI token** (from your HikerAPI dashboard)
- [`uv`](https://docs.astral.sh/uv/) for environment + dependency management

---

### Setup with `uv`

From the project root (`Instagram_Parser/`):

```bash
# 1. Make sure uv is installed (one time)
pip install uv

# 2. Install dependencies from pyproject/requirements
uv sync
```

You can now run the tool with `uv run` (no manual venv juggling needed).

---

### Configure HikerAPI credentials

Set your HikerAPI token in **one** of these environment variables:

- `HIKER_API_TOKEN`
- `HIKER_API_KEY`

Example (Linux/macOS):

```bash
export HIKER_API_TOKEN="YOUR_HIKER_API_TOKEN_HERE"
```

Alternatively, pass it explicitly via the CLI:

```bash
uv run python instagram_accounts_topk.py --token "YOUR_HIKER_API_TOKEN_HERE" ...
```

---

### CLI usage

Basic run:

```bash
uv run python instagram_accounts_topk.py \
  --query "психолог" \
  --max-accounts 300 \
  --recent-reels 30 \
  --top-k 10 \
  --output-prefix outputs/psychologist
```

**Arguments:**

- **`--query`** (required): keyword for account search (can be Cyrillic/Unicode)
- **`--max-accounts`**: max number of accounts to process (default: `200`)
- **`--recent-reels`**: how many recent reels per account to request from HikerAPI (default: `50`)
- **`--top-k`**: how many best reels to keep per account after ranking (default: `10`)
- **`--token`**: HikerAPI token override (otherwise `HIKER_API_TOKEN` / `HIKER_API_KEY` are used)
- **`--output-prefix`**: base path for output files (default: `outputs/instagram_accounts`)

---

### Outputs

For `--output-prefix outputs/psychologist` the tool writes:

- **`outputs/psychologist_accounts.jsonl`**  
  One JSON object per line:
  - `account`: normalized account fields (id, username, surname, follower counts, etc.)
  - `top_reels`: list of that account’s Top‑K reels

- **`outputs/psychologist_accounts.csv`**  
  Flat table of accounts with columns:
  - `id`, `username`, `full_name`, `surname`, `biography`, `external_url`  
  - `follower_count`, `following_count`, `media_count`, `is_verified`, `is_private`

- **`outputs/psychologist_reels.csv`**  
  Flat table of reels (each row linked back to the account):
  - `account_id`, `account_username`  
  - `media_id`, `code`, `taken_at`, `views`, `like_count`, `comment_count`, `caption_text`, `permalink`

Reels are already **ranked per account** by:

1. views (descending)  
2. timestamp (`taken_at`, descending)

---

### Notes & troubleshooting

- If HikerAPI balance is exhausted or the key is invalid, HikerAPI may return payloads with  
  `{"state": false, "error": "...", "exc_type": "..."}`. The script logs these and writes details to
  `error_log.jsonl` in the project root.
- Network/API errors are also appended to `error_log.jsonl` with stack traces for later debugging.

For full [HikerAPI](https://hikerapi.com/) reference and response structures, see the  
[official HikerAPI Python documentation](https://hiker-doc.readthedocs.io/en/latest/python.html).

