"""Create the public updater feed asset after packaging the final Windows ZIP.

python tools/make_update_manifest.py VERSION WINDOWS_ZIP --notes RELEASE_NOTES --output update.json
Upload update.json alongside the matching ZIP to the same stable GitHub Release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("zip", type=Path)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--output", type=Path, default=Path("update.json"))
    args = parser.parse_args()
    if not re.fullmatch(r"\d{1,5}\.\d{1,5}\.\d{1,5}", args.version):
        parser.error("Expected MAJOR.MINOR.PATCH")
    expected = f"StrongholdAssistant-v{args.version}-windows-x64.zip"
    if args.zip.name != expected:
        parser.error("Windows archive must be named " + expected)
    with args.zip.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    data = {"schema": 1, "version": args.version,
            "url": f"https://github.com/Fuppppping/stronghold-assistant/releases/download/v{args.version}/{expected}",
            "sha256": sha, "size": args.zip.stat().st_size,
            "notes": args.notes.read_text(encoding="utf-8") if args.notes else ""}
    if len(data["notes"]) > 16000:
        parser.error("Release notes exceed 16000 characters")
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
