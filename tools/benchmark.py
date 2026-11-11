"""Measure recognition separately from capture, using caller-supplied screenshots."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image
from stronghold.domain import Season
from stronghold.vision import Recognizer


def main():
    parser = argparse.ArgumentParser(description='识别耗时基准；不输出 OCR 原文或账号信息')
    parser.add_argument('images', nargs='+', type=Path)
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--no-cache', action='store_true', help='每次清空画面和 OCR 缓存，测试新内容开销')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error('--repeat 至少为 1')
    recognizer, results = Recognizer(Season()), []
    for index, path in enumerate(args.images, 1):
        with Image.open(path) as image:
            frame = image.convert('RGB')
        times, reused = [], []
        for _ in range(args.repeat):
            if args.no_cache:
                recognizer.reset_cache()
            start = time.perf_counter()
            reading = recognizer.inspect(frame)
            times.append(round((time.perf_counter()-start)*1000, 2))
            reused.append(reading.reused)
        row = {'sample':index, 'size':frame.size, 'scene':reading.scene, 'hit_count':len(reading.hits),
               'milliseconds':times, 'reused':reused, 'median_ms':round(statistics.median(times),2)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if args.output:
        args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    main()
