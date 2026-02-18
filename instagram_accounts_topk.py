"""
Find Instagram accounts by keyword (HikerAPI) and list Top-K reels per account.
Uses non-deprecated APIs only: fbsearch_accounts_v3, user_by_id_v2, user_clips.
"""
import argparse
import asyncio
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exception
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from hikerapi import AsyncClient

load_dotenv()

AccountDict = Dict[str, Any]
MediaDict = Dict[str, Any]

ACCOUNT_CSV_FIELDS = (
    "id", "username", "full_name", "surname", "biography", "external_url",
    "follower_count", "following_count", "media_count", "is_verified", "is_private",
)
REEL_CSV_FIELDS = (
    "account_id", "account_username", "media_id", "code", "taken_at", "views",
    "like_count", "comment_count", "caption_text", "permalink",
)


@dataclass
class AccountWithReels:
    account: AccountDict
    top_reels: List[MediaDict]


def log_error(context: str, **info: Any) -> None:
    """Append a debug record to error_log.jsonl."""
    record: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "context": context,
        **{k: v for k, v in info.items() if k != "_exc"},
    }
    exc = info.get("_exc")
    if exc is not None:
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
        record["traceback"] = "".join(format_exception(type(exc), exc, exc.__traceback__))
    try:
        Path("error_log.jsonl").open("a", encoding="utf-8").write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )
    except Exception:
        pass


def get_token(cli_token: Optional[str]) -> str:
    token = cli_token or os.getenv("HIKER_API_TOKEN") or os.getenv("HIKER_API_KEY")
    if not token:
        raise RuntimeError("Set HIKER_API_TOKEN or pass --token")
    return token


async def search_accounts(
    client: AsyncClient, query: str, max_accounts: int
) -> List[AccountDict]:
    """Search accounts by keyword using fbsearch_accounts_v3 (paginated, non-deprecated)."""
    candidates: List[AccountDict] = []
    page_token: Optional[str] = None

    while len(candidates) < max_accounts:
        try:
            res = await client.fbsearch_accounts_v3(query, page_token=page_token)
        except Exception as e:
            print(f"[WARN] fbsearch_accounts_v3 failed: {e}", file=sys.stderr)
            log_error("fbsearch_accounts_v3", query=query, _exc=e)
            break

        if not isinstance(res, dict):
            break
        # HikerAPI can return error payload instead of data
        if res.get("state") is False:
            err = res.get("error") or res.get("exc_type") or "Unknown API error"
            print(f"[WARN] API error: {err}", file=sys.stderr)
            break

        users = res.get("users") or []
        candidates.extend(users)

        # Pagination: different API versions may use page_token or next_page_token
        page_token = res.get("page_token") or res.get("next_page_token")
        has_more = res.get("has_more")
        if not has_more or not page_token or len(candidates) >= max_accounts:
            break

    # Deduplicate by pk, cap
    seen: set = set()
    deduped: List[AccountDict] = []
    for u in candidates:
        pk = str(u.get("pk") or u.get("id") or "")
        if pk and pk not in seen:
            seen.add(pk)
            deduped.append(u)
            if len(deduped) >= max_accounts:
                break
    return deduped


async def fetch_profile(
    client: AsyncClient, raw_user: AccountDict
) -> Optional[AccountDict]:
    """Fetch full profile by id using user_by_id_v2 (non-deprecated).

    HikerAPI v2 responses are usually wrapped, e.g. {"state": true, "user": {...}}.
    This function returns the inner user dict so the rest of the code works
    with a flat profile object.
    """
    pk = raw_user.get("pk") or raw_user.get("id")
    if not pk:
        return None
    try:
        profile = await client.user_by_id_v2(str(pk))
    except Exception as e:
        print(f"[WARN] user_by_id_v2 failed for pk={pk}: {e}", file=sys.stderr)
        log_error("user_by_id_v2", pk=str(pk), username=raw_user.get("username"), _exc=e)
        return None
    if not isinstance(profile, dict):
        return None
    if profile.get("state") is False:
        # API-level error, e.g. InsufficientFunds or not found
        log_error("user_by_id_v2_state_false", pk=str(pk), payload=profile)
        return None
    # Unwrap common shapes: {"user": {...}}, {"data": {...}}, or already flat
    inner = profile.get("user") or profile.get("data") or profile
    return inner if isinstance(inner, dict) else None


async def fetch_reels(
    client: AsyncClient, user_id: str, count: int
) -> List[MediaDict]:
    """Fetch up to count reels using user_clips helper (handles pagination)."""
    try:
        clips = await client.user_clips(user_id=str(user_id), count=count)
    except Exception as e:
        print(f"[WARN] user_clips failed for user_id={user_id}: {e}", file=sys.stderr)
        log_error("user_clips", user_id=str(user_id), requested_count=count, _exc=e)
        return []
    return clips[:count] if isinstance(clips, list) else []


def normalize_profile(raw: AccountDict, profile: Optional[AccountDict]) -> AccountDict:
    """Normalize to stable schema; surname = last token of full_name."""
    src = profile or raw
    pk = str(src.get("pk") or raw.get("pk") or src.get("id") or "")
    full_name = src.get("full_name") or raw.get("full_name")
    parts = full_name.strip().split() if isinstance(full_name, str) else []
    return {
        "id": pk,
        "username": src.get("username") or raw.get("username"),
        "full_name": full_name,
        "surname": parts[-1] if len(parts) >= 2 else None,
        "biography": src.get("biography"),
        "external_url": src.get("external_url"),
        "follower_count": src.get("follower_count"),
        "following_count": src.get("following_count"),
        "media_count": src.get("media_count"),
        "is_verified": src.get("is_verified"),
        "is_private": src.get("is_private"),
    }


def normalize_clip(
    raw: MediaDict, account_id: str, account_username: Optional[str]
) -> MediaDict:
    """Normalize reel to stable schema."""
    media_id = str(raw.get("pk") or raw.get("id") or "")
    code = raw.get("code") or raw.get("shortcode")
    taken_at = raw.get("taken_at") or raw.get("taken_at_timestamp") or raw.get("timestamp")
    if isinstance(taken_at, dict):
        taken_at = taken_at.get("timestamp")
    views = raw.get("play_count") or raw.get("view_count") or raw.get("video_view_count")
    like_count = raw.get("like_count")
    if like_count is None and isinstance(raw.get("edge_liked_by"), dict):
        like_count = raw["edge_liked_by"].get("count")
    comment_count = raw.get("comment_count")
    if comment_count is None and isinstance(raw.get("edge_media_to_comment"), dict):
        comment_count = raw["edge_media_to_comment"].get("count")
    caption_text = raw.get("caption_text")
    if caption_text is None and "caption" in raw:
        cap = raw["caption"]
        caption_text = cap.get("text") or cap.get("caption_text") if isinstance(cap, dict) else (cap if isinstance(cap, str) else None)
    permalink = f"https://www.instagram.com/reel/{code}/" if code and account_username else None
    return {
        "media_id": media_id,
        "code": code,
        "taken_at": taken_at,
        "views": views,
        "like_count": like_count,
        "comment_count": comment_count,
        "caption_text": caption_text,
        "permalink": permalink,
        "account_id": account_id,
        "account_username": account_username,
    }


def select_top_k(reels: Iterable[MediaDict], k: int) -> List[MediaDict]:
    """Sort by views desc, then taken_at desc; return first k."""
    def key(r: MediaDict) -> Tuple[int, int]:
        v = r.get("views")
        t = r.get("taken_at") or 0
        try:
            t = int(t)
        except (TypeError, ValueError):
            t = 0
        return (-(int(v) if isinstance(v, (int, float)) else 0), -t)
    return sorted(reels, key=key)[:k]


async def process_accounts(
    client: AsyncClient,
    query: str,
    max_accounts: int,
    recent_reels: int,
    top_k: int,
) -> List[AccountWithReels]:
    """Search -> fetch profile + reels per account -> normalize -> top-k."""
    print(f"[INFO] Searching accounts for '{query}' ...", file=sys.stderr)
    candidates = await search_accounts(client, query, max_accounts)
    print(f"[INFO] Found {len(candidates)} candidate accounts", file=sys.stderr)

    results: List[AccountWithReels] = []
    sem = asyncio.Semaphore(10)

    async def one(raw: AccountDict) -> None:
        async with sem:
            pk = raw.get("pk") or raw.get("id")
            username = raw.get("username")
            print(f"[INFO] Processing {username} (pk={pk})", file=sys.stderr)
            profile = await fetch_profile(client, raw)
            if not profile:
                print(f"[WARN] Skipping {username}: no profile", file=sys.stderr)
                return
            norm = normalize_profile(raw, profile)
            clips = await fetch_reels(client, norm["id"], recent_reels)
            norm_clips = [normalize_clip(c, norm["id"], norm["username"]) for c in clips]
            top = select_top_k(norm_clips, top_k)
            results.append(AccountWithReels(account=norm, top_reels=top))

    await asyncio.gather(*[asyncio.create_task(one(u)) for u in candidates])
    results.sort(key=lambda a: (a.account.get("follower_count") or 0), reverse=True)
    return results


def main_async(args: argparse.Namespace) -> None:
    client = AsyncClient(token=get_token(args.token))
    data = asyncio.run(
        process_accounts(
            client, args.query, args.max_accounts, args.recent_reels, args.top_k
        )
    )
    if not data:
        print("[INFO] No accounts with reels found.", file=sys.stderr)
        return
    out_dir = Path(args.output_prefix)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    base = out_dir.with_suffix("") if out_dir.suffix else out_dir
    base_str = str(base)

    with Path(base_str + "_accounts.jsonl").open("w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps({"account": item.account, "top_reels": item.top_reels}, ensure_ascii=False) + "\n")
    with Path(base_str + "_accounts.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ACCOUNT_CSV_FIELDS)
        w.writeheader()
        for item in data:
            w.writerow(item.account)
    with Path(base_str + "_reels.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REEL_CSV_FIELDS)
        w.writeheader()
        for item in data:
            for r in item.top_reels:
                w.writerow(r)
    print(f"[INFO] Wrote {base_str}_accounts.jsonl, _accounts.csv, _reels.csv", file=sys.stderr)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find IG accounts by keyword (HikerAPI), list Top-K reels per account.")
    p.add_argument("--query", required=True, help="Search keyword")
    p.add_argument("--max-accounts", type=int, default=200)
    p.add_argument("--recent-reels", type=int, default=50)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--token", help="HikerAPI token (or HIKER_API_TOKEN env)")
    p.add_argument("--output-prefix", default="outputs/instagram_accounts")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    try:
        main_async(args)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted.", file=sys.stderr)


if __name__ == "__main__":
    main()
