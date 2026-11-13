"""Compare a tagged recognizer and the current one on identical caller images."""
import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from PIL import Image
from stronghold import VERSION
from stronghold.domain import Season
from stronghold.vision import Recognizer, game_region


def baseline(ref):
    source=subprocess.check_output(['git','show',f'{ref}:stronghold/vision.py'],cwd=ROOT).decode('utf8')
    name='stronghold._comparison_baseline'
    spec=importlib.util.spec_from_loader(name,loader=None)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    exec(compile(source,f'<git {ref}:stronghold/vision.py>','exec'),module.__dict__)
    return module.Recognizer


def signature(reading):
    result=asdict(reading)
    for field in ('elapsed_ms','capture_ms','reused'):
        result.pop(field,None)
    return result


def main():
    parser=argparse.ArgumentParser(description='配对测速并核对业务字段；JSON结果不含OCR原文或输入文件路径')
    parser.add_argument('images',nargs='+',type=Path)
    parser.add_argument('--baseline',default='v0.3.10')
    parser.add_argument('--repeat',type=int,default=8)
    parser.add_argument('--change-rect',nargs=4,type=int,default=(985,380,1000,395),metavar=('X1','Y1','X2','Y2'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not re.fullmatch(r'v?\d+\.\d+\.\d+',args.baseline):
        parser.error('--baseline 需要已存在的版本标签，例如v0.3.10')
    if args.repeat<1:
        parser.error('--repeat 至少为1')
    a,b,c,d=args.change_rect
    if not 0<=a<c<=1280 or not 0<=b<d<=720:
        parser.error('--change-rect 需要1280×720范围内的非空矩形')
    cases=[]
    for index,path in enumerate(args.images,1):
        with Image.open(path) as image:
            frame=image.convert('RGB')
        left,top,right,bottom=game_region(frame)
        rect=(left+round(a*(right-left)/1280),top+round(b*(bottom-top)/720),
              left+round(c*(right-left)/1280),top+round(d*(bottom-top)/720))
        variants=[]
        for i in range(args.repeat):
            variant=frame.copy()
            step=i%11
            variant.paste((20+step*20,90+step*10,150-step*10),rect)
            variants.append(variant)
        cases.extend([(index,'static',frame,[frame]*args.repeat),(index,'background-probe',frame,variants)])
    results=[]
    expected={}
    for is_baseline,version,cls in ((True,args.baseline,baseline(args.baseline)),(False,VERSION,Recognizer)):
        recognizer=cls(Season())
        for index,kind,original,frames in cases:
            recognizer.reset_cache()
            recognizer.inspect(original)
            times,meanings=[],[]
            for frame in frames:
                start=time.perf_counter()
                reading=recognizer.inspect(frame)
                times.append(round((time.perf_counter()-start)*1000,2))
                meanings.append(signature(reading))
            key=index,kind
            if is_baseline:
                expected[key]=meanings
            elif meanings!=expected[key]:
                raise AssertionError(f'样本{index} {kind} 的业务识别字段不一致')
            row=dict(version=version,sample=index,kind=kind,size=original.size,repeat=args.repeat,
                     changed_rect=args.change_rect if kind=='background-probe' else None,
                     milliseconds=times,median_ms=round(statistics.median(times),2),
                     scene=reading.scene,hit_count=len(reading.hits))
            results.append(row)
            print(json.dumps(row,ensure_ascii=False),flush=True)
    payload=dict(scope='CPU recognition after warm-up; excludes capture, model loading and fixture construction',
                 semantic_fields_equal=True,results=results)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS all semantic fields match across paired static and artificial-background probes',flush=True)


if __name__=='__main__':
    main()
