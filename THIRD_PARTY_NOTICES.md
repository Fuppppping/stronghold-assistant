# 第三方来源与许可

本文件记录 0.3.x 的参考项目、实际依赖、模型、规则和素材来源。原始许可文本位于 [licenses/](licenses/)，构建环境中的版本与许可文件校验值见 [DEPENDENCIES.json](DEPENDENCIES.json)。应用原创代码采用 [MIT](LICENSE)，该许可不覆盖下面列出的第三方作品。

`docs/screenshots/` 为本项目界面的离线回放演示。其中游戏画面来自本机 PC 客户端的已记录帧，游戏图像与角色版权归鹰角网络及相关权利人所有；紧凑浮层图由本项目实际提示渲染器在离线画面上展示，不代表实时识别结果或官方界面。未使用生成式图片制作这些演示图。

## 参考代码与 SDK

| 项目 | 在本项目中的用途 | 上游与许可 |
| --- | --- | --- |
| MaaAssistantArknights（MAA） | 参考截图、ROI、图像模板及官方 PC 控制方案；从 `resource/battle_data.json` 提取简中干员名，形成 `data/operator_names.json`。未集成 MAA 主程序、任务流水线或自动作战资源 | [仓库](https://github.com/MaaAssistantArknights/MaaAssistantArknights) · [名称数据](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/resource/battle_data.json) · [PC 端参考讨论](https://github.com/MaaAssistantArknights/MaaAssistantArknights/pull/18256) · 上游 [AGPL-3.0](licenses/references/MAA-AGPL-3.0.txt) |
| MaaFramework / MaaFw | 实际依赖 `MaaFw 5.15.0`。`stronghold/pc_input.py` 使用 Win32Controller、原始分辨率截图和 `PostMessageWithCursorPos`，仅执行显式的商店展开/收起单步操作 | [固定版本源码](https://github.com/MaaXYZ/MaaFramework/tree/v5.15.0) · [Python 接口示例](https://github.com/MaaXYZ/MaaFramework/blob/v5.15.0/sample/python/demo1.py) · [LGPL-3.0](licenses/maafw/maafw-5.15.0.dist-info/licenses/LICENSE.md) |
| Microsoft Win32 API | `stronghold/windows.py` 与 `overlay.py` 通过 Python ctypes 使用窗口枚举、抓屏、置顶、鼠标穿透和非激活窗口样式 | [Windows API](https://learn.microsoft.com/windows/win32/api/) · 系统接口，Windows 不随源码重新分发 |

本项目的 Python 界面、识别整合、本局状态、攻略排序和提示逻辑位于 `stronghold/`。MAA 与 MaaFramework 是不同项目；“参考 MAA”并不表示由 MAA 官方开发或维护。

MaaFramework 原始源码未作修改。公开 Release 同时提供对应版本的上游源码归档。用户可从源码运行或重新打包，也可用 MaaFw 已提供的 `MAAFW_BINARY_PATH` 指定兼容的替代动态库目录：

```powershell
$env:MAAFW_BINARY_PATH = 'C:\MyMaaFramework\bin'
.\StrongholdAssistant.exe
```

目录需要包含兼容版本的 `MaaFramework.dll`、`MaaToolkit.dll` 及所需依赖。该环境变量由 [MaaFw 的库加载入口](https://github.com/MaaXYZ/MaaFramework/blob/v5.15.0/source/binding/Python/maa/__init__.py) 读取。LGPL 和其引用的 GPL 文本随发布包保留在 `licenses/`。

## 主要运行组件

| 组件 | 本次构建版本 | 用途 | 来源 / 许可 |
| --- | --- | --- | --- |
| Python / tkinter | Python 3.12.10；Tcl/Tk 8.6 | 解释器、桌面 UI、透明浮层 | [CPython](https://github.com/python/cpython/tree/v3.12.10)、[Tcl/Tk](https://www.tcl.tk/) · PSF 及 Tcl/Tk 许可，见 `licenses/python`、`licenses/tcl`、`licenses/tk` |
| RapidOCR | 3.10.0 | 本地文字检测、识别 | [RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) · Apache-2.0 |
| ONNX Runtime | 1.31.1 | CPU 模型推理 | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) · MIT；原生依赖声明见 `licenses/onnxruntime` |
| OpenCV Python Headless | 5.0.0.93 | 模板匹配、轮廓、颜色和图像预处理 | [opencv-python](https://github.com/opencv/opencv-python)、[OpenCV](https://github.com/opencv/opencv) · Apache-2.0；原生依赖声明见 `licenses/opencv-python-headless` |
| NumPy | 2.5.4 | 数组计算 | [numpy/numpy](https://github.com/numpy/numpy) · BSD-3-Clause 及其附带子组件许可 |
| Pillow | 13.0.0 | 抓屏、图像读取、裁剪、缩放 | [python-pillow/Pillow](https://github.com/python-pillow/Pillow) · MIT-CMU 及附带图像编解码库声明 |
| PyInstaller | 6.22.3（构建工具） | Windows 打包与引导程序 | [pyinstaller/pyinstaller](https://github.com/pyinstaller/pyinstaller) · GPL-2.0-or-later，含 bootloader exception，原文见 `licenses/pyinstaller` |

间接依赖包括 pyclipper、six、Shapely/GEOS、PyYAML、tqdm、OmegaConf、requests、colorlog、flatbuffers、packaging、protobuf、StrEnum、colorama、charset-normalizer、idna、urllib3、certifi。其本次安装版本、主页、许可证和原始声明均保留在 `DEPENDENCIES.json` 与 `licenses/`，不统一改为 MIT。

MaaFw 安装依赖中还包含 [MaaAgentBinary](https://github.com/MaaXYZ/MaaAgentBinary) 1.0.1（AGPL-3.0）。它提供 Android 触控代理；当前 PC 路径没有使用这些代理，Windows 打包参数没有收集其代理资源。开发环境的许可副本仍保留在 `licenses/maaagentbinary`。

MaaFw 的原生 DLL 包还带有 DirectML、DirectX Shader Compiler、FastDeploy、ONNX Runtime、OpenCV、Dawn/WebGPU、ViGEmClient 等依赖；这些文件来自未修改的 MaaFw 发行包，版本以其发行构建为准，不应与上表的 Python 包版本混同。上游分别是 [DirectML](https://github.com/microsoft/DirectML)、[DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler)、[FastDeploy](https://github.com/PaddlePaddle/FastDeploy)、[ONNX Runtime](https://github.com/microsoft/onnxruntime)、[OpenCV](https://github.com/opencv/opencv)、[Dawn](https://dawn.googlesource.com/dawn)、[ViGEmClient](https://github.com/nefarius/ViGEmClient)。构建入口和依赖版本记录见 MaaFramework 对应版本源码中的构建配置。

## OCR 模型

模型由 [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 上游提供，RapidOCR 转换/封装为 ONNX。模型版权归百度及相应 PaddleOCR 权利人，适用 Apache-2.0；模型与 RapidOCR 代码分别署名。完整声明见 [MODEL_LICENSES.md](licenses/rapidocr/rapidocr-3.10.0.dist-info/licenses/MODEL_LICENSES.md)。

| 包内文件 | 用途 | 上游 |
| --- | --- | --- |
| `PP-OCRv6_det_small.onnx` | 文本检测 | [PaddlePaddle/PP-OCRv6_small_det_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv6_small_det_onnx) |
| `PP-OCRv6_rec_small.onnx` | 中英文文字识别 | [PaddlePaddle/PP-OCRv6_small_rec_onnx](https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx) |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | RapidOCR 附带的方向分类模型；当前识别调用关闭方向分类 | [PaddleOCR 模型列表](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/model_list.en.md) |

模型文件未修改。其实际 SHA-256 已写入 `DEPENDENCIES.json`。源码仓库不提交模型权重；Windows 体验包内含模型，源码运行时由 RapidOCR 按其默认配置获取。

## 规则、攻略和游戏素材

| 本地内容 | 来源 | 整理方式与署名 |
| --- | --- | --- |
| `data/season.json` 的干员、盟约、策略、装备字段 | [PRTS 本期盟约记录](https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录)、[战场一览](https://prts.wiki/w/卫戍协议·规程/战场一览)，通过 [SquadPool 图鉴](https://squad-pool.com/arknights-pacts) 的结构化资料整理 | 2026-11-10～11-11 整理；筛选、重命名字段以适配识别和攻略。PRTS 衍生文字按上游声明的 [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/) 保留署名、非商业和相同方式共享要求 |
| `data/season.json` 中的阵容、阶段、思路、叠层角色及装备建议 | [SquadPool 阵容索引](https://squad-pool.com/arknights-pacts)，以及各阵容 `sources` 中原作者的 B 站视频/图文 | 对攻略作摘要、改写和字段化；三个分支是本项目的整理方案。原视频、图文及其表达的版权属于原作者，不视为本项目原创或统一纳入 MIT |
| `data/head/*.webp`、`data/pact/*.webp`、`data/strat/*.webp` | SquadPool 的 `assets/ark-pacts/{head,pact,strat}/`，其资料页注明美术经 PRTS 取自游戏 | 原始游戏头像、图标用于图像识别，未宣称取得其原创版权。游戏名称、美术及商标归鹰角网络及相应权利人；这些素材不属于 MIT 授权范围 |
| `data/operator_names.json` | MAA `dev-v2/resource/battle_data.json` | 提取简中名称并合并为识别字典，保留来源；未复制 MAA 自动化任务代码 |

内置攻略署名包括白樱iridescent、白绮Infinity、晓杰425、自在道爷等。全部作者和直达链接以每套攻略的 `sources` 为准。代表性来源：

- [白樱iridescent：规程通用叠层与经济卡](https://www.bilibili.com/video/BV1ZBW46eEdW/)
- [白绮Infinity：伊比利亚思路分享](https://www.bilibili.com/video/BV1k1WW6AEx7/)
- [阿戈尔实战](https://www.bilibili.com/video/BV1FnWn6XEA5/)
- [本期核心盟约叠层一图流](https://www.bilibili.com/opus/1268367330752069664)
- [旧版共享卡池实测](https://www.bilibili.com/video/BV1JWy3BkEpt/)；只作估算逻辑参考，未据此硬编码本期总池量。

验证所用的 PC 截图、账号画面和原始视频不放入公开仓库。官方机制说明来源为 [本期活动公告](https://ak.hypergryph.com/news/0787.html) 与 [官方演示](https://www.bilibili.com/video/BV18RHN64EZV?p=2)。本项目与上述项目、攻略作者和游戏官方不存在维护或背书关系。

## 再分发

分发 Windows 体验包时保留 `LICENSE`、`THIRD_PARTY_NOTICES.md`、`DEPENDENCIES.json`、`licenses/` 及上游来源说明。修改数据或第三方组件时需继续保留其各自的来源与许可，不能仅根据本项目根目录的 MIT 许可重新授权游戏素材、模型或攻略。
