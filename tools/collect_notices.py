"""Collect installed dependency attribution without copying user-specific paths."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
DIRECT = ['rapidocr', 'onnxruntime', 'Pillow', 'numpy', 'opencv-python-headless', 'MaaFw']
FALLBACK = {'maafw': 'LGPL-3.0', 'maaagentbinary': 'AGPL-3.0', 'strenum': 'MIT',
            'omegaconf': 'BSD-3-Clause', 'colorama': 'BSD-3-Clause'}


def collect():
    queue, seen, records = DIRECT+['pyinstaller'], set(), []
    while queue:
        name = queue.pop(0).lower().replace('_', '-')
        if name in seen:
            continue
        seen.add(name)
        distribution = metadata.distribution(name)
        notices = []
        for file in distribution.files or []:
            relative = str(file).replace('\\', '/')
            if not any(part in relative.lower() for part in ('license', 'licence', 'notice', 'copying')):
                continue
            source = distribution.locate_file(file)
            if not source.is_file() or source.suffix.lower() in {'.py', '.pyc', '.dll', '.pyd'}:
                continue
            # Keep the complete package-relative path to disambiguate embedded native notices.
            target = ROOT/'licenses'/name/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_bytes()
            target.write_bytes(content)
            notices.append({'path': target.relative_to(ROOT).as_posix(),
                            'sha256': hashlib.sha256(content).hexdigest()})
        records.append({'name': distribution.metadata['Name'], 'version': distribution.version,
                        'license': distribution.metadata.get('License-Expression')
                            or distribution.metadata.get('License') or FALLBACK.get(name, 'See upstream'),
                        'project_urls': distribution.metadata.get_all('Project-URL') or [],
                        'home_page': distribution.metadata.get('Home-page') or '', 'notices': notices})
        if name != 'pyinstaller':
            for raw in distribution.requires or []:
                requirement = Requirement(raw)
                if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                    queue.append(requirement.name)
    base = Path(sys.base_prefix)
    for source, target in [(base/'LICENSE.txt', ROOT/'licenses/python/LICENSE.txt'),
                           (base/'tcl/tk8.6/license.terms', ROOT/'licenses/tk/license.terms')]:
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    models = []
    for file in metadata.distribution('rapidocr').files or []:
        if str(file).endswith('.onnx'):
            source = metadata.distribution('rapidocr').locate_file(file)
            models.append({'file': str(file).replace('\\', '/'), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    payload = {'scope': 'Build-environment dependency closure and notices; not a binary load inventory',
               'python': sys.version.split()[0], 'direct_requirements': DIRECT,
               'packages': sorted(records, key=lambda record: record['name'].lower()), 'ocr_models': models}
    (ROOT/'DEPENDENCIES.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(f'Collected notices for {len(records)} distributions and hashes for {len(models)} OCR models')


if __name__ == '__main__':
    collect()
