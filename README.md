# 卫戍协议助手

帮你看这一局能玩什么，选好阵容后，想找的干员和装备出现时提醒你。适用于简中《明日方舟》PC 客户端，也支持能正常抓屏的模拟器。

**[下载 Windows 版](https://github.com/Fuppppping/stronghold-assistant/releases/latest)** · 当前版本 **0.3.5** · 解压后直接运行，不用安装 Python。

## 局中能帮什么

下面用离线回放演示，画面里的记录不是当前对局。

**像游戏插件一样放在旁边。** 点主窗口底栏的「悬浮窗模式」，大窗口就会收起，换成可拖动的小面板。阵容思路、叠层清单、来牌和装备提醒一起看；面板位置可以自己摆。

![可拖动悬浮面板与游戏内来牌提示，使用离线回放演示](docs/screenshots/04-compact-overlay.png)

**商店里有想找的卡，提醒你别漏。** 金色看核心和关键装备，青绿看可用叠层。小窗里有监测、攻略、干员、BAN、装备和设置六页，可以直接选阵容、改装备提醒、查看队友卡池。长内容可以滚动。

<img src="docs/screenshots/01-live-help.png" width="400" alt="悬浮窗近景：阵容思路、核心与可用叠层、装备和来牌提醒">

**开局先看谁被 BAN。** 读到有效盟约后就会推算禁用干员；向下滚动游戏的 BAN 名单，还会继续补读。名单会写明是推算出来的，还是直接识别到的。

![本局 BAN 名单和禁用依据](docs/screenshots/02-ban-evidence.png)

**选阵容时，会把缺的关键卡列出来。** 推荐会检查整套卡的 BAN 情况，包括核心、叠层和功能位。分数只是当前卡池的适配程度，不是胜率；替代卡也不保证一样强。

![阵容排序、缺牌和攻略详情](docs/screenshots/03-lineup-guide.png)

## 怎么用

1. 完整解压下载的压缩包，运行 `StrongholdAssistant.exe`，再打开游戏。助手会寻找客户端；有多个窗口时可以手动选。
2. 进入卫戍协议的「确认本局信息」，等助手读出盟约和 BAN。有误的盟约可以双击校正。
3. 在「阵容攻略」选定想玩的阵容。之后的干员、策略和装备提示会跟着这套攻略走。
4. 装备不一定要跟攻略：在「装备提醒」里自行勾选或屏蔽。屏蔽的装备不会再提醒。
5. 重开新局后，本局 BAN、已见干员和队友快照会自动清空；选定攻略和个人偏好会保留。

左侧切换页面，也可以用 `Ctrl + 1–6`。普通识别不需要管理员权限；「展开商店 / 收起商店」这两个 PC 单步按钮需要以管理员身份运行助手。

## 悬浮窗怎么用

- **移动、缩放**：拖动顶栏移动，拖右下角缩放。位置、尺寸、不透明度和模式会记住。
- **收起**：点顶栏「收起」只留一条标题栏，再点「展开」恢复。
- **穿透**：点「穿透」后，内容区的点击会直接落到游戏；顶栏仍能拖动、解锁和返回主窗口。
- **返回主窗**：点顶栏「主窗」。导入攻略、手动校正和高级采集设置也会回到主窗口处理。
- **调外观**：在悬浮窗「设置」里调整字号与不透明度，也能恢复默认位置。

切成悬浮窗后，识别继续运行，阵容和本局记录共用同一份数据。游戏卡片附近的小提示可以单独开关；固定在左上的文字思路会收进面板，避免重复显示。悬浮窗保持置顶，切到其他软件时也会保留，需要时可收起或返回主窗。

在助手内按 `Ctrl + Shift + F` 也能切换模式。分辨率变化或断开副屏后，会把面板移回可见区域。

## 提示太大或太小？

打开「采集设置」，拖动「浮层字号」即可，范围是 **80%–200%**，调整后即时生效并记住。默认是 **135%**，比 0.3.3 大约增加三分之一；「恢复默认」可以一键重置。

普通模式仍使用左上透明文字；悬浮窗模式把这些信息放进面板。可以在设置中关闭游戏卡片附近的小提示。

## 更新

启动后会在后台检查新版本，之后每 6 小时检查一次。发现更新只在底栏提示，不会在对局中替你安装。自动检查可以在设置中关闭。

点击底栏或「采集设置 → 程序更新」，先下载，等方便的时候再点「安装并重启」。下载会校验完整性，安装前会备份；新版启动失败时会尝试恢复旧版。设置和导入的攻略都会保留。

**0.3.2 及更早版本没有更新入口，需要手动下载新版一次。0.3.3 起可以在程序内更新。**

如果 GitHub 连不上，稍后重试或从发布页手动下载。程序所在文件夹需要可写；更新过程不会主动请求管理员权限。同一游戏窗口还开着时，更新重启可恢复 15 分钟内的本局记录。

## 攻略与自定义

目前内置 **13 条阵容和运营分支**。每条保留来源，可以点「打开攻略来源」看原视频。攻略的前、中、后期是参考节奏，助手暂时不会按回合自动切换阶段。

有自己的打法，可以在「阵容攻略 → JSON 格式与模板」另存模板，改完再导入。先看 [攻略示例](guide.example.json)；完整字段写在 [攻略 JSON 格式](攻略JSON格式.md) 里。`plan` 是常驻思路，`stacking` 用来区分核心和可用叠层，`requirements` 用来写关键位和替代候选。

## 队友阵容和剩余卡池

打开游戏里的队友总览，助手会按从上到下的「面板1–4」记录可见干员。重复看到同一面板时会覆盖旧快照，不会把商店里没买的卡算进去。星级看不清时只记占用下限，可以在「禁用卡池 → 队友阵容 / 共享卡池」手动校正。

**余量是估算，不能当精确记牌器。** 当前版本的总池量还没可靠核实，默认只显示已见占用；你设置总池量后，才会给出余量范围。暂按普通1份、精锐3份计算，星极精锐按2份。没看到的备战区、赠送牌和记录时差都会影响结果；30秒没更新会提示过期。队友行顺序变了，需要清掉旧行再读。

机制参考：[共享卡池实测](https://www.bilibili.com/video/BV1JWy3BkEpt/)、[本期官方演示](https://www.bilibili.com/video/BV18RHN64EZV?p=2)。

## 识别不对时

- 抓不到画面：把游戏切到前台，试试窗口化或无边框模式。模拟器也可以在采集设置里改用 ADB。
- BAN 少了：向下滚动游戏名单，让助手继续读；无法确认的内容会保留为待确认。
- 换了皮肤后漏识别：当前头像模板覆盖固定池143名干员，自选干员和皮肤可能漏读。可以导入截图回放检查。
- 提醒慢：主窗口底部会分别显示采集和识别耗时。已做区域复用和缓存，具体测试范围见 [性能说明](PERFORMANCE.md)。

这版主要按简中、横屏和常见终端主题校准。它会读画面、给建议，不能自动打完整对局；PC 单步按钮也只会展开或收起商店。

## 设置放在哪里

个人设置、导入攻略和日志都在 `%LOCALAPPDATA%\StrongholdAssistant`。更新缓存和备份放在其中的 `updates` 文件夹；确认程序正常并关闭所有助手后，可以清理旧任务来腾空间。源码运行可用 `STRONGHOLD_STATE` 改位置。

## 从源码运行

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

离线识别和规则测试：

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --inspect screenshot.png --output result.json
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

打包前安装 `pyinstaller==6.22.3`，然后执行 `build.ps1`。源码仓库不包含 OCR 权重，首次运行可能需要下载模型；Windows 发布包已经带好模型。修改第三方依赖后，用 `tools/collect_notices.py` 更新声明，发布时保留 `licenses` 文件夹。

<details>
<summary>维护者：怎样发布程序内更新</summary>

先改 `stronghold/__init__.py` 的版本号，打包最终的 Windows ZIP，并附上 `SOURCE_PROVENANCE.json`。然后生成更新清单：

```powershell
python tools/make_update_manifest.py 0.3.5 StrongholdAssistant-v0.3.5-windows-x64.zip --notes release-notes.md --output update.json
```

把 ZIP 和 `update.json` 上传到对应的 `v0.3.5` 正式 Release，再设为最新版本。清单中的版本、大小、SHA-256 和包内来源信息要一致；不要上传后再替换包。更新客户端只接受已管理的程序、文档、演示图和许可路径，新增文件前要考虑旧客户端的兼容性。预发布版不会走这个更新通道。

更新通过本仓库的 HTTPS Release 清单分发。SHA-256 用来检查下载损坏，当前没有独立代码签名；源码运行可以检查和下载，自动安装仅支持打包程序。

</details>

## 参考代码与组件

参考了 MAA 的截图、ROI、模板识别和 PC 控制思路，也用到它的简中干员名称字典。实际单步输入用的是 MaaFramework。界面、本局状态、攻略整合和提醒逻辑在本仓库实现，没有集成 MAA 主程序。

| 项目 / 组件 | 用途 | 来源 |
| --- | --- | --- |
| MAA | 设计参考、PC 方案与干员名称字典；上游 AGPL-3.0 | [MAA 源码](https://github.com/MaaAssistantArknights/MaaAssistantArknights)、[battle_data.json](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/resource/battle_data.json)、[PC 参考讨论](https://github.com/MaaAssistantArknights/MaaAssistantArknights/pull/18256) |
| MaaFramework / MaaFw 5.15.0 | Win32 单步控制与截图接口；LGPL-3.0 | [固定版本源码](https://github.com/MaaXYZ/MaaFramework/tree/v5.15.0)、[Python 示例](https://github.com/MaaXYZ/MaaFramework/blob/v5.15.0/sample/python/demo1.py) |
| RapidOCR 3.10.0 | 本地 OCR；Apache-2.0 | [RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) |
| PaddleOCR PP-OCRv6 | 文本检测、识别模型，RapidOCR 提供 ONNX 封装；Apache-2.0 | [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| ONNX Runtime 1.31.1 | CPU 推理；MIT | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) |
| OpenCV Headless 5.0.0.93 | 图像处理和模板匹配；Apache-2.0 | [OpenCV Python](https://github.com/opencv/opencv-python) |
| NumPy 2.5.4 / Pillow 13.0.0 | 数组运算、抓屏、图像转换；BSD 系 / MIT-CMU 等 | [NumPy](https://github.com/numpy/numpy)、[Pillow](https://github.com/python-pillow/Pillow) |
| Python 3.12 / tkinter / ctypes | 桌面 UI、窗口浮层、Windows 系统接口 | [CPython](https://github.com/python/cpython)、[Tcl/Tk](https://www.tcl.tk/)、[Win32 API](https://learn.microsoft.com/windows/win32/api/) |
| PyInstaller 6.22.3 | Windows 打包；GPL 含 bootloader exception | [PyInstaller](https://github.com/pyinstaller/pyinstaller) |
| PRTS / SquadPool | 本期干员、盟约、策略、装备及阵容资料；图标与头像来自游戏 | [PRTS 图鉴](https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录)、[SquadPool](https://squad-pool.com/arknights-pacts) |

完整的组件、模型、素材来源和许可证见 [第三方说明](THIRD_PARTY_NOTICES.md) 与 [依赖清单](DEPENDENCIES.json)。攻略作者和原链接保留在各条攻略的 `sources` 中；演示图来自本项目的离线回放，游戏画面归鹰角网络及相关权利人所有。

原创代码和文档采用 [MIT](LICENSE)。PRTS 衍生文字保留 CC BY-NC-SA 3.0；第三方模型、组件、游戏素材和攻略各按原许可处理，不会因为放进这个仓库就变成 MIT。转发体验包时，请保留来源说明和许可证目录。

这是玩家工具，与鹰角、MAA、MaaFramework 及攻略作者没有隶属关系。版本改动见 [更新记录](CHANGELOG.md)。
