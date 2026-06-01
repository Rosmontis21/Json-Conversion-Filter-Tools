import argparse
import json
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".avi",
    ".mov",
    ".flv",
    ".wmv",
    ".m4v",
}


def normalize_id(value):
    value = str(value or "").strip()
    if value.startswith("v_"):
        return value[2:]
    return value


def collect_video_index(video_dir, recursive):
    video_dir = Path(video_dir)
    pattern = "**/*" if recursive else "*"
    index = {}

    for path in video_dir.glob(pattern):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue

        stem = path.stem
        for key in {stem, normalize_id(stem)}:
            index.setdefault(key, []).append(str(path))

    return index


def find_near_matches(video_index, video_id, limit=5):
    normalized = normalize_id(video_id)
    if not normalized:
        return []

    matches = []
    for candidate_id, paths in video_index.items():
        if normalized in candidate_id or candidate_id in normalized:
            for path in paths:
                matches.append(path)
                if len(matches) >= limit:
                    return matches
    return matches


def expected_filenames(video_id):
    normalized = normalize_id(video_id)
    names = []
    for base in dict.fromkeys([str(video_id or "").strip(), normalized]):
        if not base:
            continue
        names.extend([f"{base}{ext}" for ext in sorted(VIDEO_EXTENSIONS)])
    return names


def load_json_array(path):
    with Path(path).open("r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be a JSON array.")
    return data


def default_state_path(path):
    path = Path(path)
    return path.with_name(f"{path.name}.filter_state.json")


def load_state(path):
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def same_path(left, right):
    if not left or not right:
        return False
    return str(Path(left).resolve()).lower() == str(Path(right).resolve()).lower()


def choose_state_path(input_path, output_path, explicit_state_file):
    if explicit_state_file:
        path = Path(explicit_state_file)
        return path, path

    input_state_path = default_state_path(input_path)
    output_state_path = default_state_path(output_path)

    if input_state_path.exists():
        return input_state_path, output_state_path
    if output_state_path.exists():
        return output_state_path, output_state_path
    return input_state_path, output_state_path


def choose_start(args_start, state, input_path, record_count):
    if args_start is not None:
        return args_start
    if not state:
        return 0

    state_input = state.get("input", "")
    state_output = state.get("output", "")

    if same_path(input_path, state_output):
        return int(state.get("next_filtered_start", state.get("next_start", 0)))
    if same_path(input_path, state_input):
        return int(state.get("next_original_start", state.get("next_start", 0)))

    previous_output_count = state.get("output_record_count")
    previous_input_count = state.get("input_record_count")
    if previous_output_count == record_count:
        return int(state.get("next_filtered_start", state.get("next_start", 0)))
    if previous_input_count == record_count:
        return int(state.get("next_original_start", state.get("next_start", 0)))

    return int(state.get("next_filtered_start", state.get("next_start", 0)))


def selected_records(records, start, limit):
    if start < 0:
        raise ValueError("--start must be 0 or a positive integer.")
    if limit < 0:
        raise ValueError("--limit must be 0 or a positive integer.")
    records = records[start:]
    if limit == 0:
        return records
    return records[:limit]


def get_video_id(record):
    if isinstance(record, dict):
        if "video_id" in record:
            return record.get("video_id")
        nested = record.get("record")
        if isinstance(nested, dict) and "video_id" in nested:
            return nested.get("video_id")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Keep only annotation records whose video_id has a matching local video file."
    )
    parser.add_argument("--input", required=True, help="JSON array file to check")
    parser.add_argument("--video-dir", required=True, help="Folder containing downloaded videos")
    parser.add_argument("--output", required=True, help="Filtered JSON output file")
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="Start checking from this 0-based record index; omit to continue from saved state",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Check N records from --start; use 0 to check all remaining records",
    )
    parser.add_argument(
        "--deleted-output",
        default="",
        help="Optional JSON file listing records removed because no video file was found",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search video files recursively under --video-dir",
    )
    parser.add_argument(
        "--state-file",
        default="",
        help="Progress state JSON path; defaults to a sidecar file next to --input/--output",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    read_state_path, write_state_path = choose_state_path(input_path, output_path, args.state_file)
    state = load_state(read_state_path)

    records = load_json_array(input_path)
    start = choose_start(args.start, state, input_path, len(records))
    records_to_check = selected_records(records, start, args.limit)
    video_index = collect_video_index(args.video_dir, args.recursive)

    checked_kept = []
    deleted = []
    missing_id = []

    for offset, record in enumerate(records_to_check):
        index = start + offset
        video_id = get_video_id(record)
        normalized = normalize_id(video_id)

        if not video_id:
            missing_id.append(index)
            deleted.append(
                {
                    "index": index,
                    "video_id": "",
                    "normalized_video_id": "",
                    "reason": "missing video_id field",
                    "expected_filenames": [],
                    "near_matches": [],
                    "record": record,
                }
            )
            continue

        matched_paths = video_index.get(video_id) or video_index.get(normalized)
        if matched_paths:
            checked_kept.append(record)
        else:
            deleted.append(
                {
                    "index": index,
                    "video_id": video_id,
                    "normalized_video_id": normalized,
                    "reason": "no matching video file found",
                    "expected_filenames": expected_filenames(video_id),
                    "near_matches": find_near_matches(video_index, video_id),
                    "record": record,
                }
            )

    end = start + len(records_to_check)
    output_records = records[:start] + checked_kept + records[end:]
    next_original_start = end
    next_filtered_start = start + len(checked_kept)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_records, f, ensure_ascii=False, indent=2)

    save_state(
        write_state_path,
        {
            "input": str(input_path),
            "output": str(output_path),
            "video_dir": str(Path(args.video_dir)),
            "input_record_count": len(records),
            "output_record_count": len(output_records),
            "last_start": start,
            "last_limit": args.limit,
            "last_checked": len(records_to_check),
            "last_kept": len(checked_kept),
            "last_deleted": len(deleted),
            "next_original_start": next_original_start,
            "next_filtered_start": next_filtered_start,
            "next_start": next_filtered_start,
            "note": "If the next input is the original JSON, use next_original_start. If the next input is the filtered output JSON, use next_filtered_start. When --start is omitted, the script chooses automatically.",
        },
    )

    deleted_output = args.deleted_output
    if deleted_output:
        deleted_path = Path(deleted_output)
        deleted_path.parent.mkdir(parents=True, exist_ok=True)
        with deleted_path.open("w", encoding="utf-8") as f:
            json.dump(deleted, f, ensure_ascii=False, indent=2)

    print(f"Input records loaded: {len(records)}")
    print(f"Start index: {start}")
    print(f"Records checked: {len(records_to_check)}")
    print(f"Video ids/stems found: {len(video_index)}")
    print(f"Kept records in checked range: {len(checked_kept)}")
    print(f"Deleted records: {len(deleted)}")
    print(f"Output records written: {len(output_records)}")
    print(f"Next original-file start index: {next_original_start}")
    print(f"Next filtered-file start index: {next_filtered_start}")
    if missing_id:
        print(f"Records missing video_id: {len(missing_id)}")
    print(f"Wrote filtered JSON: {output_path}")
    print(f"Wrote progress state: {write_state_path}")
    if deleted_output:
        print(f"Wrote deleted-record log: {deleted_output}")


if __name__ == "__main__":
    main()
