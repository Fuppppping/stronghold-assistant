"""Entry point for the desktop app and offline image inspection."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="卫戍协议助手")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect", type=Path, help="离线识别一张截图并输出 JSON")
    mode.add_argument("--pc-shop", choices=("open", "close"), help="单步展开或收起前台 PC 客户端的调度中心")
    parser.add_argument("--scene", default="", help="为 --inspect 指定场景")
    parser.add_argument("--output", type=Path, help="将命令结果写入 UTF-8 JSON 文件")
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
        write_result(payload, args.output)
    elif args.pc_shop:
        from stronghold import windows
        from stronghold.app import SETTINGS_DIR
        from stronghold.domain import Season
        from stronghold.pc_input import operate_shop
        from stronghold.vision import Recognizer

        windows.enable_dpi()
        try:
            if not windows.is_admin():
                raise RuntimeError("PC 单步操作需要以管理员身份运行")
            result = operate_shop(windows.foreground(), args.pc_shop, Recognizer(Season()), SETTINGS_DIR / "maa")
        except (RuntimeError, OSError) as exc:
            write_result({"ok": False, "message": str(exc)}, args.output)
            raise SystemExit(1)
        write_result({"ok": True, "message": result}, args.output)
    else:
        from stronghold.app import run
        run()


def write_result(payload, output):
    result_json = json.dumps(payload, ensure_ascii=False, indent=2)
    if output:
        output.write_text(result_json + "\n", encoding="utf-8")
    else:
        print(result_json)


if __name__ == "__main__":
    main()
