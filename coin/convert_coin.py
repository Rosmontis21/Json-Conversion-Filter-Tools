import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path


def sentence_case(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    return text


def camel_to_sentence(text):
    text = str(text or "").replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return sentence_case(text)


def as_number(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def limited_items(items, limit):
    if limit < 0:
        raise ValueError("--limit must be 0 or a positive integer")
    items = list(items)
    if limit == 0:
        return items
    return items[:limit]


def progress_items(items, label):
    total = len(items)
    if total == 0:
        return

    width = 30
    for index, item in enumerate(items, start=1):
        filled = int(width * index / total)
        bar = "#" * filled + "-" * (width - filled)
        percent = index * 100 / total
        sys.stdout.write(f"\r{label}: [{bar}] {index}/{total} ({percent:5.1f}%)")
        sys.stdout.flush()
        yield item
    sys.stdout.write("\n")
    sys.stdout.flush()


def convert_record(video_id, record):
    annotations = record.get("annotation") or []
    subtasks = []
    bad_reasons = []

    for index, item in enumerate(annotations):
        label = item.get("label", "")
        segment = item.get("segment")
        if not isinstance(segment, list) or len(segment) != 2:
            bad_reasons.append(f"annotation {index} has invalid segment")
            continue

        subtasks.append(
            OrderedDict(
                [
                    ("subtask_id", str(item.get("id", index))),
                    ("name", sentence_case(label)),
                    ("segment", [as_number(segment[0]), as_number(segment[1])]),
                    ("segment_unit", "seconds"),
                    ("exists", True),
                    ("completed", True),
                    ("source_text", label),
                ]
            )
        )

    source_split = record.get("subset", "")
    dataset_class = record.get("class", "")
    recipe_type = record.get("recipe_type", "")

    converted = OrderedDict(
        [
            ("source_dataset", "COIN"),
            ("source_split", source_split or ""),
            ("sample_type", "procedural"),
            ("video_id", video_id),
            ("video_url", record.get("video_url", "") or ""),
            ("video_path", ""),
            ("duration_sec", as_number(record.get("duration"))),
            ("goal", camel_to_sentence(dataset_class)),
            ("subtasks", subtasks),
            (
                "meta",
                OrderedDict(
                    [
                        ("original_task_id", str(recipe_type) if recipe_type != "" else ""),
                        ("original_label", dataset_class or ""),
                        (
                            "note",
                            f"source_start={record.get('start', '')}; source_end={record.get('end', '')}",
                        ),
                    ]
                ),
            ),
        ]
    )
    return converted, bad_reasons


def main():
    parser = argparse.ArgumentParser(description="Convert COIN annotations to unified JSON format.")
    parser.add_argument("--input", required=True, help="Path to COIN.json")
    parser.add_argument("--output-dir", required=True, help="Directory for converted output files")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of source records to convert; use 0 to convert all records",
    )
    parser.add_argument(
        "--raw-name",
        default="raw_coin_100.json",
        help='Raw sample output filename; use "none" to skip writing the raw file',
    )
    parser.add_argument("--converted-name", default="converted_coin.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    database = payload.get("database", {})
    write_raw = args.raw_name.lower() != "none"
    raw_records = []
    converted_records = []
    bad_records = []

    selected_items = limited_items(database.items(), args.limit)

    for video_id, record in progress_items(selected_items, "Converting COIN"):
        if write_raw:
            raw_records.append(OrderedDict([("video_id", video_id), ("record", record)]))
        converted, reasons = convert_record(video_id, record)
        converted_records.append(converted)
        if reasons:
            bad_records.append({"video_id": video_id, "reasons": reasons})

    if write_raw:
        with (output_dir / args.raw_name).open("w", encoding="utf-8") as f:
            json.dump(raw_records, f, ensure_ascii=False, indent=2)

    with (output_dir / args.converted_name).open("w", encoding="utf-8") as f:
        json.dump(converted_records, f, ensure_ascii=False, indent=2)

    if bad_records:
        with (output_dir / "bad_coin_records.json").open("w", encoding="utf-8") as f:
            json.dump(bad_records, f, ensure_ascii=False, indent=2)

    if write_raw:
        print(f"Wrote {len(raw_records)} raw COIN records")
    else:
        print("Skipped raw COIN output")
    print(f"Wrote {len(converted_records)} converted COIN records")
    print(f"Bad COIN records: {len(bad_records)}")


if __name__ == "__main__":
    main()
