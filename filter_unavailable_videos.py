import argparse
import json
import sys
from pathlib import Path


try:
    import yt_dlp
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "yt-dlp is required. Install it with: pip install yt-dlp"
    ) from exc


def normalize_id(value):
    value = str(value or "").strip()
    if value.startswith("v_"):
        return value[2:]
    return value


def youtube_watch_url(video_id):
    video_id = normalize_id(video_id)
    if not video_id:
        return ""
    return f"https://www.youtube.com/watch?v={video_id}"


def get_video_id(record):
    if isinstance(record, dict):
        if "video_id" in record:
            return record.get("video_id")
        nested = record.get("record")
        if isinstance(nested, dict) and "video_id" in nested:
            return nested.get("video_id")
    return None


def load_json(path):
    with Path(path).open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def iter_list_records(records, start, limit):
    if start < 0:
        raise ValueError("--start must be 0 or a positive integer")
    if limit < 0:
        raise ValueError("--limit must be 0 or a positive integer")
    sliced = records[start:]
    if limit != 0:
        sliced = sliced[:limit]
    return sliced, start


def iter_database_records(database, start, limit):
    items = list(database.items())
    if start < 0:
        raise ValueError("--start must be 0 or a positive integer")
    if limit < 0:
        raise ValueError("--limit must be 0 or a positive integer")
    sliced = items[start:]
    if limit != 0:
        sliced = sliced[:limit]
    return sliced, start


def make_ydl(cookies_path):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    if not cookies_path:
        default_cookies = Path.home() / "Downloads" / "yt-dlp-youtube-cookies.txt"
        cookies_path = str(default_cookies) if default_cookies.exists() else ""
    if cookies_path and Path(cookies_path).exists():
        options["cookiefile"] = str(Path(cookies_path))
    return yt_dlp.YoutubeDL(options)


def is_downloadable(ydl, video_id, video_url):
    url = youtube_watch_url(video_id) or video_url
    if not url:
        return False, "missing video_url and video_id"

    try:
        info = ydl.extract_info(url, download=False)
    except Exception as exc:
        return False, str(exc)

    if not info:
        return False, "empty metadata"

    availability = str(info.get("availability") or "").lower()
    if availability in {
        "unavailable",
        "private",
        "needs_auth",
        "premium_only",
        "subscriber_only",
        "geo_restricted",
        "deleted",
        "live_stream_offline",
        "post_live_stream_offline",
    }:
        return False, f"availability={availability or 'unknown'}"

    title = str(info.get("title") or "").lower()
    if "video unavailable" in title:
        return False, "title indicates unavailable"

    return True, ""


def progress(index, total, prefix):
    width = 30
    filled = int(width * index / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    percent = (index * 100 / total) if total else 100
    sys.stdout.write(f"\r{prefix}: [{bar}] {index}/{total} ({percent:5.1f}%)")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="Remove records whose YouTube videos are not downloadable."
    )
    parser.add_argument("--input", required=True, help="JSON file to inspect")
    parser.add_argument("--output", required=True, help="Filtered JSON output file")
    parser.add_argument(
        "--deleted-output",
        default="",
        help="Optional JSON file recording removed items and reasons",
    )
    parser.add_argument(
        "--cookies",
        default="",
        help="Optional cookies file for yt-dlp, useful for age-restricted videos",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start from this 0-based index",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Check N records from --start; use 0 to check all remaining records",
    )
    args = parser.parse_args()

    payload = load_json(args.input)
    ydl = make_ydl(args.cookies)

    kept = []
    deleted = []

    if isinstance(payload, list):
        selected, start = iter_list_records(payload, args.start, args.limit)
        total = len(selected)
        for offset, record in enumerate(selected, start=1):
            index = start + offset - 1
            video_id = get_video_id(record)
            video_url = record.get("video_url", "") if isinstance(record, dict) else ""
            ok, reason = is_downloadable(ydl, video_id, video_url)
            progress(offset, total, "Checking videos")
            if ok:
                kept.append(record)
            else:
                deleted.append(
                    {
                        "index": index,
                        "video_id": video_id or "",
                        "video_url": video_url or youtube_watch_url(video_id),
                        "reason": reason,
                        "record": record,
                    }
                )
        print()
        output_data = payload[:start] + kept + payload[start + total :]

    elif isinstance(payload, dict) and isinstance(payload.get("database"), dict):
        items, start = iter_database_records(payload["database"], args.start, args.limit)
        total = len(items)
        new_database = dict()
        before = list(payload["database"].items())[:start]
        after = list(payload["database"].items())[start + total :]
        for key, record in before:
            new_database[key] = record
        for offset, (key, record) in enumerate(items, start=1):
            video_id = key
            video_url = record.get("video_url", "") if isinstance(record, dict) else ""
            ok, reason = is_downloadable(ydl, video_id, video_url)
            progress(offset, total, "Checking videos")
            if ok:
                new_database[key] = record
                kept.append({"video_id": video_id, "record": record})
            else:
                deleted.append(
                    {
                        "index": start + offset - 1,
                        "video_id": video_id,
                        "video_url": video_url or youtube_watch_url(video_id),
                        "reason": reason,
                        "record": record,
                    }
                )
        print()
        for key, record in after:
            new_database[key] = record
        output_data = dict(payload)
        output_data["database"] = new_database
    else:
        raise ValueError("Input JSON must be a list or a dict containing a 'database' object.")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json(output_path, output_data)

    if args.deleted_output:
        save_json(args.deleted_output, deleted)

    print(f"Kept records: {len(kept)}")
    print(f"Deleted records: {len(deleted)}")
    print(f"Wrote filtered JSON: {output_path}")
    if args.deleted_output:
        print(f"Wrote deleted-record log: {args.deleted_output}")


if __name__ == "__main__":
    main()
