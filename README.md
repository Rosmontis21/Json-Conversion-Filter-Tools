# COIN / ActivityNet Captions Conversion Tools

This folder contains scripts for converting and filtering COIN and ActivityNet Captions annotations.

## Scripts

- `coin/convert_coin.py`
  Converts COIN annotations to the unified JSON array format.
- `activitynet_captions/convert_activitynet_captions.py`
  Converts ActivityNet Captions annotations to the unified JSON array format.
- `filter_annotations_by_videos.py`
  Keeps only annotation records whose `video_id` has a matching local video file.
- `filter_unavailable_videos.py`
  Uses `yt-dlp` to check whether each YouTube video is still available without downloading it. Unavailable videos are removed.

## Convert COIN

Open PowerShell:

```powershell
cd "C:\Users\ASUS\Desktop\convert\coin"
```

Convert the first 100 records:

```powershell
python .\convert_coin.py `
  --input "D:\gitContent\annotations\COIN.json" `
  --output-dir "." `
  --limit 100 `
  --raw-name "raw_coin_100.json" `
  --converted-name "converted_coin.json"
```

Convert all records:

```powershell
python .\convert_coin.py `
  --input "D:\gitContent\annotations\COIN.json" `
  --output-dir "." `
  --limit 0 `
  --raw-name "none" `
  --converted-name "converted_coin_all.json"
```

`--raw-name "none"` means no raw sample JSON will be written.

## Convert ActivityNet Captions

Open PowerShell:

```powershell
cd "C:\Users\ASUS\Desktop\convert\activitynet_captions"
```

Convert the first 100 training records:

```powershell
python .\convert_activitynet_captions.py `
  --input "C:\Users\ASUS\Desktop\Video_test\ActivityNet Captions\captions\train.json" `
  --output-dir "." `
  --limit 100 `
  --split training `
  --raw-name "raw_activitynet_captions_100.json" `
  --converted-name "converted_activitynet_captions.json"
```

Convert all records:

```powershell
python .\convert_activitynet_captions.py `
  --input "C:\Users\ASUS\Desktop\Video_test\ActivityNet Captions\captions\train.json" `
  --output-dir "." `
  --limit 0 `
  --split training `
  --raw-name "none" `
  --converted-name "converted_activitynet_captions_all.json"
```

## Filter By Local Video Files

Use this when you already downloaded videos and want to remove annotations whose video file is missing.

Open PowerShell:

```powershell
cd "C:\Users\ASUS\Desktop\convert"
```

Example:

```powershell
python .\filter_annotations_by_videos.py `
  --input "C:\Users\ASUS\Desktop\convert\coin\converted_coin.json" `
  --video-dir "C:\Users\ASUS\Desktop\COIN" `
  --start 0 `
  --limit 100 `
  --output "C:\Users\ASUS\Desktop\convert\coin\converted_coin_filtered.json" `
  --deleted-output "C:\Users\ASUS\Desktop\convert\coin\deleted_coin_records.json"
```

If videos are inside subfolders, add:

```powershell
--recursive
```

Useful options:

- `--start 30 --limit 100`: check 100 records starting from index 30.
- Omit `--start`: continue from the saved progress state if it exists.
- `--limit 0`: check all remaining records.

The script writes a progress state file named like:

```text
converted_coin_filtered.json.filter_state.json
```

This file contains the next item from the last last checked position: `--next_start`

If you continue filtering, use the previous filtered JSON as the next `--input`.

## Filter By YouTube Availability

Use this when you want to check whether YouTube videos are still available without downloading them.

This script requires `yt-dlp`:

```powershell
pip install yt-dlp
```

Open PowerShell:

```powershell
cd "C:\Users\ASUS\Desktop\convert"
```

Example:

```powershell
python .\filter_unavailable_videos.py `
  --input "C:\Users\ASUS\Desktop\convert\coin\converted_coin.json" `
  --output "C:\Users\ASUS\Desktop\convert\coin\converted_coin_available.json" `
  --deleted-output "C:\Users\ASUS\Desktop\convert\coin\deleted_unavailable_coin.json"
```

Check only a slice:

```powershell
python .\filter_unavailable_videos.py `
  --input "C:\Users\ASUS\Desktop\convert\coin\converted_coin.json" `
  --start 100 `
  --limit 100 `
  --output "C:\Users\ASUS\Desktop\convert\coin\converted_coin_available_100_100.json" `
  --deleted-output "C:\Users\ASUS\Desktop\convert\coin\deleted_unavailable_coin_100_100.json"
```

Optional cookies file:

```powershell
--cookies "C:\Users\ASUS\Downloads\yt-dlp-youtube-cookies.txt"
```

If `--cookies` is omitted, the script automatically tries:

```text
C:\Users\ASUS\Downloads\yt-dlp-youtube-cookies.txt
```

## Important Notes

- All output JSON files are JSON arrays except when filtering an original COIN `COIN.json`, which keeps the original `database` structure.
- `--limit 0` means all records.
- `--raw-name "none"` means skip raw JSON output.
- Deleted-record logs are strongly recommended because they show exactly which `video_id` was removed and why.
