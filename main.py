"""Entry point for the desktop app and offline image inspection."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="卫戍协议助手")
    parser.add_argument("--inspect", type=Path, help="离线识别一张截图并输出 JSON")
    parser.add_argument("--scene", default="", help="为 --inspect 指定场景")
    parser.add_argument("--output", type=Path, help="将 --inspect 的结果写入 UTF-8 JSON 文件")
    args = parser.parse_args()
    if args.inspect:
        from PIL import Image
        from stronghold.domain import Season
        from stronghold.vision import Recognizer

        with Image.open(args.inspect) as frame:
            result = Recognizer(Season()).inspect(frame.convert("RGB"), args.scene)
        payload = asdict(result)
        payload["excluded"] = sorted(result.excluded)
        payload["groups"] = [sorted(group) for group in result.groups]
        result_json = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(result_json + "\n", encoding="utf-8")
        else:
            print(result_json)
    else:
        from stronghold.app import run
        run()


if __name__ == "__main__":
    main()
