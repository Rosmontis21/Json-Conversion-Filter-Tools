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


def as_number(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def youtube_url(video_id):
    if not video_id:
        return ""
    public_id = video_id[2:] if video_id.startswith("v_") else video_id
    return f"https://www.youtube.com/watch?v={public_id}"


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


def convert_record(video_id, record, source_split):
    timestamps = record.get("timestamps") or []
    sentences = record.get("sentences") or []
    subtasks = []
    bad_reasons = []

    count = min(len(timestamps), len(sentences))
    if len(timestamps) != len(sentences):
        bad_reasons.append(
            f"timestamps count {len(timestamps)} does not match sentences count {len(sentences)}"
        )

    for index in range(count):
        sentence = sentences[index]
        segment = timestamps[index]
        if not isinstance(segment, list) or len(segment) != 2:
            bad_reasons.append(f"event {index} has invalid timestamp")
            continue

        subtasks.append(
            OrderedDict(
                [
                    ("subtask_id", str(index)),
                    ("name", sentence_case(sentence)),
                    ("segment", [as_number(segment[0]), as_number(segment[1])]),
                    ("segment_unit", "seconds"),
                    ("exists", True),
                    ("completed", True),
                    ("source_text", sentence),
                ]
            )
        )

    goal = sentence_case(sentences[0]) if sentences else ""
    converted = OrderedDict(
        [
            ("source_dataset", "ActivityNet Captions"),
            ("source_split", source_split),
            ("sample_type", "event_caption"),
            ("video_id", video_id),
            ("video_url", youtube_url(video_id)),
            ("video_path", ""),
            ("duration_sec", as_number(record.get("duration"))),
            ("goal", goal),
            ("subtasks", subtasks),
            (
                "meta",
                OrderedDict(
                    [
                        ("original_task_id", video_id),
                        ("original_label", ""),
                        ("note", "Dense event captions; goal is populated from the first caption."),
                    ]
                ),
            ),
        ]
    )
    return converted, bad_reasons


def infer_split(path):
    stem = Path(path).stem.lower()
    if stem == "train":
        return "training"
    if stem.startswith("val"):
        return "validation"
    if stem == "test":
        return "testing"
    return stem


def main():
    parser = argparse.ArgumentParser(
        description="Convert ActivityNet Captions annotations to unified JSON format."
    )
    parser.add_argument("--input", required=True, help="Path to train.json, val_1.json, or val_2.json")
    parser.add_argument("--output-dir", required=True, help="Directory for converted output files")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of source records to convert; use 0 to convert all records",
    )
    parser.add_argument("--split", default="", help="Override source split")
    parser.add_argument(
        "--raw-name",
        default="raw_activitynet_captions_100.json",
        help='Raw sample output filename; use "none" to skip writing the raw file',
    )
    parser.add_argument("--converted-name", default="converted_activitynet_captions.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_split = args.split or infer_split(input_path)

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    write_raw = args.raw_name.lower() != "none"
    raw_records = []
    converted_records = []
    bad_records = []

    selected_items = limited_items(payload.items(), args.limit)

    for video_id, record in progress_items(selected_items, "Converting ActivityNet Captions"):
        if write_raw:
            raw_records.append(OrderedDict([("video_id", video_id), ("record", record)]))
        converted, reasons = convert_record(video_id, record, source_split)
        converted_records.append(converted)
        if reasons:
            bad_records.append({"video_id": video_id, "reasons": reasons})

    if write_raw:
        with (output_dir / args.raw_name).open("w", encoding="utf-8") as f:
            json.dump(raw_records, f, ensure_ascii=False, indent=2)

    with (output_dir / args.converted_name).open("w", encoding="utf-8") as f:
        json.dump(converted_records, f, ensure_ascii=False, indent=2)

    if bad_records:
        with (output_dir / "bad_activitynet_captions_records.json").open("w", encoding="utf-8") as f:
            json.dump(bad_records, f, ensure_ascii=False, indent=2)

    if write_raw:
        print(f"Wrote {len(raw_records)} raw ActivityNet Captions records")
    else:
        print("Skipped raw ActivityNet Captions output")
    print(f"Wrote {len(converted_records)} converted ActivityNet Captions records")
    print(f"Bad ActivityNet Captions records: {len(bad_records)}")


if __name__ == "__main__":
    main()
