# 卫戍协议助手

面向 Windows 的《明日方舟》卫戍协议·规程（序列 I）桌面助手。程序读取游戏画面，在前台游戏窗口上方显示鼠标穿透标记。数据和 OCR 模型随 Windows 版本提供，识别在本机运行。

## 开始使用

1. 打开 `StrongholdAssistant.exe`，再打开简中《明日方舟》或承载游戏的模拟器。助手会寻找客户端窗口。若识别到多个实例，可在下拉框手动绑定。
2. 进入卫戍协议的「确认本局信息」。助手读取亮起与置灰的盟约，并在「盟约与可用池」按羁绊显示干员。个人模拟的二选一会列出两组。「阵容不完整」表示该组的干员池有缺员，个别干员仍可能出现。双击盟约可在手动可用、手动禁用和自动判断之间切换。
3. 在「阵容与攻略」选定阵容。轮选策略时，浮层优先标记当前可见的攻略策略。调度中心展开后，匹配的核心干员、过渡干员和装备会在对应卡片上方标记。
4. 在「装备提示」选择装备后点击「勾选提醒」「屏蔽」或「跟随攻略」。勾选和屏蔽会保留到下一次启动，屏蔽优先。未选阵容时也可以勾选装备。
5. 到下一局时，若旧 BAN 仍显示，在「盟约与可用池」点击「新一局 / 清除 BAN」。

「实时识别」可以导入截图回放，也可查看最近采集帧。抓屏失败时，把游戏切到前台。模拟器若提供 ADB，可在「采集设置」填写可执行文件和已连接的设备序列号，再勾选 ADB 采集。ADB 只提供图像，窗口绑定仍负责浮层定位。

目前按简中界面、横屏和常见终端主题校准。边缘被裁切、被其他窗口遮住、低分辨率或第三方主题可能影响识别。少量只显示头像的禁用干员需要在游戏内查看名单。可用池按本局盟约和已识别禁用名单推算，预备干员替换和自选编队中的个人选择以游戏为准。后台 GPU 抓屏与独占全屏的行为取决于客户端，推荐窗口化或无边框窗口。

## 自定义攻略

在「阵容与攻略」导入 [攻略示例](guide.example.json)。修改 `id` 为唯一标识后，可指定成型羁绊、阶段、干员、策略顺位和装备备注。名称使用游戏内简中全名。装备提醒可以在界面继续覆盖。

## 从源码运行

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

离线诊断单帧，默认自动判断场景。`--scene` 可指定 `调度中心`、`盟约选择`、`策略轮选`、`自选编队` 或 `装备选择`。
`--output result.json` 将诊断结果保存到文件，免安装版本也可使用。

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --inspect screenshot.png
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

打包需要先安装 `pyinstaller==6.22.3`，再在仓库根目录执行 `build.ps1`。本地设置、导入的攻略及运行日志在 `%LOCALAPPDATA%\StrongholdAssistant`，可用 `STRONGHOLD_STATE` 指定其他位置。

## 资料

- 客户端识别设计参考 MAA 的截图、ROI 和图像模板工作流。项目使用 RapidOCR 的 PP-OCR 模型。 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) · [MaaFramework](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/en_us/1.1-QuickStarted.md) · [RapidOCR](https://github.com/RapidAI/RapidOCR)
- 序列 I 的规则与图鉴来自游戏说明和 PRTS。阵容阶段、策略建议及装备提示参考社区图鉴和各阵容的实战攻略，出处可在应用中打开。盟约和策略图标用于画面识别，游戏素材版权归其权利人。 [官方公告](https://ak.hypergryph.com/news/0787.html) · [PRTS 盟约记录](https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录) · [战场说明](https://prts.wiki/w/卫戍协议·规程/战场一览) · [SquadPool 阵容索引](https://squad-pool.com/arknights-pacts)
- 商店实战样本包含默认与定制终端主题。战前验证样本取自先行试玩和官方机制演示。 [阿戈尔实战](https://www.bilibili.com/video/BV1FnWn6XEA5/) · [炎国实战](https://www.bilibili.com/video/BV1BPWJ6yE3P/) · [先行试玩](https://www.bilibili.com/video/BV19P4w6aEk3/) · [前瞻演示](https://www.bilibili.com/video/BV18RHN64EZV?p=2)
