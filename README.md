# 卫戍协议助手 · Stronghold Assistant

**开局看 BAN，选阵容看缺牌，局中找叠层与关键装备。** [下载最新版 Windows 包](https://github.com/Fuppppping/stronghold-assistant/releases/latest)

下面是 **0.3.3 的离线截图回放与提示布局演示**，用于说明助手会提供哪些帮助；不代表实时对局数据。游戏画面归鹰角网络及相关权利人所有。

### 局中：来牌时提醒，战场留给游戏

选定攻略后，底部商店出现对应干员或装备时显示小标签；金色强调核心与关键装备，青绿标记可用叠层。攻略思路、核心叠层和可用叠层收在左上窄栏（约画面宽度 14%），长内容缩略，完整说明在助手窗口查看。使用小号文字与透明背景，顶部 18% 留给层数等游戏信息，作战区域不绘制干员标签。浮层置顶、鼠标穿透，不影响点击游戏。

![局中透明提示：左上窄栏常驻思路，商店的盟约之币和深靛分别提示装备与可用叠层](docs/screenshots/04-compact-overlay.png)

### 整备：常驻阵容思路，区分核心与可用

主窗口同时展示当前阶段、本局 BAN、画面提醒与识别耗时。左侧查看攻略打法和核心/可用叠层，右侧对照当前来牌；装备也可自行勾选或屏蔽。

![主窗口：当前攻略、核心与可用叠层、实时装备及干员提醒](docs/screenshots/01-live-help.png)

### 开局：先知道谁被 BAN，再决定玩什么

首帧有效盟约结果即推算禁用姓名，滚动游戏 BAN 名单会继续补读；界面标明「盟约推算」与「名单识别」，待确认项保留不确定状态。重开新局自动重置本局记录。

![开局 BAN 名单：按干员列出禁用依据、所属盟约与待确认数量](docs/screenshots/02-ban-evidence.png)

### 选阵容：按整套卡的 BAN 情况推荐

推荐检查核心、叠层卡、其他阵容卡与关键功能位，说明缺牌和候选。选中阵容后，局中提醒跟随该攻略；支持导入攻略 JSON。适配分用于衡量当前 BAN 与可用池，**不是胜率**。

![阵容攻略：整套卡牌适配排序、关键位缺牌、替代依据与常驻思路](docs/screenshots/03-lineup-guide.png)

面向 Windows 的《明日方舟》卫戍协议·规程（序列 I）桌面助手。程序读取游戏画面，在前台游戏窗口上方显示鼠标穿透标记。数据和 OCR 模型随 Windows 版本提供，识别在本机运行。

当前版本 **0.3.3**，支持简中官方 PC 客户端及可抓取画面的模拟器。该项目为玩家工具，由本仓库维护，与游戏官方、MAA、MaaFramework 和攻略作者均无隶属关系。

## 下载

前往 **[GitHub Releases 下载 Windows 体验包](https://github.com/Fuppppping/stronghold-assistant/releases/latest)**，解压整个压缩包后运行 `StrongholdAssistant.exe`，无需安装 Python。压缩包同时提供使用说明、攻略 JSON 模板及第三方许可文件。

源代码下载使用仓库的 Code → Download ZIP，或 `git clone https://github.com/Fuppppping/stronghold-assistant.git`。仓库中的源码不包含 OCR 模型权重；Release 的 Windows 程序包含模型。

## 功能

| 功能 | 当前行为 |
| --- | --- |
| 客户端绑定 | 自动寻找官方 PC 客户端或模拟器，可手动选择窗口 |
| 开局 BAN | 有效盟约首帧立即推算禁用姓名，滚动名单补读文字和标准头像，区分推算与直接识别 |
| 本局状态 | 新局自动清空旧 BAN、已见卡和队友快照，保留个人装备偏好与选定攻略 |
| 可用干员池 | 按核心、附加盟约分组，区分确认可用、禁用和待确认 |
| 攻略与策略 | 内置 13 套阵容/分支，按整套卡牌 BAN、核心与功能位候选评分，提供缺牌和替代说明 |
| 穿透浮层 | 游戏前台显示非激活置顶提示，常驻攻略思路，区分核心与可用叠层角色 |
| 装备提醒 | 跟随攻略、手动勾选或屏蔽，屏蔽优先 |
| 队友记牌 | 识别总览头像，按玩家行覆盖快照，可手动校正星级；余量为估算 |
| 离线回放 | 导入截图检查场景、识别结果与提示，无需操作游戏 |
| 程序更新 | 后台检查 GitHub 正式版，校验下载，一键安装重启，启动失败回退 |

主要限制：头像模板覆盖固定池 143 名干员；皮肤、自选干员或模糊画面可能漏识别。当前赛季总池量未可靠核实，默认显示占用下限。联机实局识别仍需继续校准，当前没有自动回合识别或完整自动对局功能。

## 开始使用

### 自动更新（0.3.3 起）

首次请手动下载并完整解压 **0.3.3 或更新版本**；0.3.2 及更早的程序没有更新入口，无法自动获得此功能。

启动约 3 秒后、此后每 6 小时检查一次 GitHub 正式版，仅在底栏和「采集设置 → 程序更新」提示，不弹窗打断游戏。可在设置中关闭自动检查，也可随时点击底栏检查。

发现新版本后，点击「下载更新」。下载、SHA-256 校验及解压在后台执行，识别继续运行；下载完成后，选择「安装并重启」。建议本局结束后安装。助手先启动独立更新助手，确认准备完成后才退出，备份旧文件、替换完整程序及随附许可文件，再启动新版。新版未能在 90 秒内完成界面初始化，会恢复旧文件并重启旧版。断网、校验失败或目录不可写时保留当前程序，可重试或手动下载。更新失败信息显示在更新窗口，并保留备份。

个人设置与导入攻略保存在 `%LOCALAPPDATA%\StrongholdAssistant`，更新不会覆盖。更新重启后，若 15 分钟内仍绑定同一游戏窗口和进程，会恢复本局 BAN、已见干员与队友快照；客户端变更、关闭或过期时不恢复，后续新局识别仍会自动重置。

程序所在文件夹须可写。更新助手沿用当前程序权限，不会主动请求管理员权限；若放在受保护目录，可移至个人可写目录后使用。源码运行支持检查和下载，安装功能仅限 Windows 打包程序。GitHub 无法连接时，请稍后重试或从发布页手动下载。

更新缓存、备份与结果位于个人目录的 `updates` 文件夹。暂不自动清除失败备份；确认程序正常并关闭所有助手后，可自行清理旧更新任务以释放空间。SHA-256 用于检测下载损坏，更新清单通过 HTTPS 从本项目公开发布页获取；当前不提供独立代码签名。

维护者发布更新时，应先更新 `stronghold/__init__.py` 中的版本号，生成最终 ZIP（含 `SOURCE_PROVENANCE.json`），再运行：

```powershell
python tools/make_update_manifest.py 0.3.4 StrongholdAssistant-v0.3.4-windows-x64.zip --notes release-notes.md --output update.json
```

将 `update.json` 与同名 Windows ZIP 上传至同一个 `v0.3.4` 正式 Release，再设为最新版本。清单中的版本、大小、SHA-256、仓库与包内来源信息必须一致；不要在上传后替换已发布的包。预发布版不会通过正式版通道推送。

### 规程终端界面

界面参考本期终端的黑灰网格、青绿信号、橙金强调与切角面板。左侧导航分为实时监测、可用干员、禁用卡池、阵容攻略、装备提醒和采集设置，支持 `Ctrl + 1–6` 切换。

首页集中显示当前阶段、BAN 数量、提醒数量和识别耗时。当前攻略的思路与适配原因单独成栏，核心叠层为金色，可用叠层为青绿；长内容可滚动。完整禁用名单和 OCR 诊断通过各自入口查看。点击「阵容详情 / 更换」会定位到当前攻略。

默认窗口为1280×900，最小1080×800；表格支持水平和垂直滚动。浮层使用小号透明文字和细定位角标，仍保持置顶、非激活和鼠标穿透。主窗口的背景和装饰为本项目的矢量绘制，没有新增主题图片、动画或第三方 UI 依赖。

1. 打开 `StrongholdAssistant.exe`，再打开简中《明日方舟》或承载游戏的模拟器。助手会寻找客户端窗口。若识别到多个实例，可在下拉框手动绑定。
2. 进入卫戍协议的「确认本局信息」。助手读取亮起与置灰的盟约，并在「盟约与可用池」按羁绊显示干员。个人模拟的二选一会列出两组，向下滚动可补读附加盟约。双击盟约可校正状态。「仅显示已确认」筛选已确认可用的干员，本局商店实际出现过的干员标为「本局已见」。
3. 在「阵容与攻略」选定阵容。轮选策略时，浮层优先标记当前可见的攻略策略；未选阵容时会根据可用池推荐当前可见的选项。调度中心展开后，匹配的核心干员、过渡干员和装备会在对应卡片上方标记。
4. 在「装备提示」选择装备后点击「勾选提醒」「屏蔽」或「跟随攻略」。勾选和屏蔽会保留到下一次启动，屏蔽优先。未选阵容时也可以勾选装备。
5. 开局第一帧有效盟约结果即推算禁用干员，完整姓名在「BAN与共享池 → 本局 BAN 名单」。向下滚动游戏禁用名单会合并补读文字和标准头像，分别标注「盟约推算」「名单识别」。无法确认的干员保持待确认。
6. 重开回到「确认本局信息」时自动清空上一局的盟约、禁用名单、已见卡与队友持有量。连续两帧难度开始页/结束页也会清空；再次查看本局信息或滚动页面不会清空。手动重置按钮保留用于识别失败时校正，装备偏好与选定攻略继续保留。

### 整套阵容推荐依据

推荐同时检查阶段核心、核心叠层卡、其他阵容卡和关键功能位，而不是只判断羁绊是否亮起。功能位候选全部被 BAN 或人数不够时，阵容先降级；仍有候选时列出缺失核心与可用候选。待确认卡保留不确定状态，不视为已经可用。

同一轮中，核心权重高于其他卡，目标人数覆盖也参与评分；当前商店来牌只作少量加分，不会压过关键位缺失。界面中的分数是 BAN 与卡池适配分，不是胜率，候选也不代表等强替换。自定义攻略可以用 `requirements` 声明功能位、候选干员及最低人数，格式见 [攻略 JSON 说明](攻略JSON格式.md)。

### 识别速度

0.3.1 增加区域复用、策略格匹配、模板与头像缓存，并避免窄条 OCR 过度放大。窗口顶部显示采集与识别耗时；本机同样本策略页从约2.88秒降至0.43秒，商店新画面约0.56–0.77秒。静态关键区域的复用时间更短，但不代表新内容的识别时间。测试范围和复现命令见 [PERFORMANCE.md](PERFORMANCE.md)。

「实时识别」可以导入截图回放，也可查看最近采集帧。抓屏失败时，把游戏切到前台。模拟器若提供 ADB，可在「采集设置」填写可执行文件和已连接的设备序列号，再勾选 ADB 采集。ADB 只提供图像，窗口绑定仍负责浮层定位。

目前按简中界面、横屏和常见终端主题校准。边缘被裁切、被其他窗口遮住、低分辨率或第三方主题可能影响识别。头像模板覆盖当前固定池 143 名干员，未覆盖的自选干员、皮肤头像和模糊头像不会强行匹配。可用池按本局盟约和已识别禁用名单推算，预备干员替换和自选编队中的个人选择以游戏为准。后台 GPU 抓屏与独占全屏的行为取决于客户端，推荐窗口化或无边框窗口。

官方 Windows 客户端 `Arknights.exe` 可直接抓取窗口，采集设置保持默认即可。PC 端已用 3840×2160 的「极速模拟」实机验证盟约二选一、四列策略、调度中心和穿透浮层。自选编队页会单独识别本局可选的账号干员。

## PC 单步操作

以管理员身份启动助手并绑定官方 PC 客户端，在卫戍协议的回合整备期使用「实时识别」页底部的「展开商店」或「收起商店」。助手切回游戏，重新读取目标按钮，再用 MaaFramework 发送一次带光标定位的点击。画面切换后显示确认结果。目标状态已经满足时直接返回。

管理员命令行也可操作已在前台的 PC 客户端。`--pc-shop open` 展开商店，`--pc-shop close` 收起商店。使用 `--output result.json` 可保存验证结果。

## 自定义攻略

在「阵容与攻略 → JSON 格式与模板」查看并另存模板，再导入 [攻略示例](guide.example.json)。完整字段见 [攻略 JSON 格式](攻略JSON格式.md)，编辑器可使用 [JSON Schema](data/guide.schema.json)。`plan` 常驻显示思路，`stacking` 的 `role` 分为 `core`（核心叠层）和 `available`（可用叠层），`note` 写触发条件。核心叠层用金色星标，可用叠层用青色文字；被禁用的角色从常驻提示中移除，`?` 表示可用性待确认。攻略详情保留被禁用项以便判断缺什么。

内置 13 套阵容与分支，补充了规程通用叠层、伊比利亚迅捷、阿戈尔助力思路。分支为助手根据列出的攻略整理，不代表原作者单独发布的阵容。通用叠层是过渡方案。攻略中的阶段是参考节奏，助手尚未自动读取回合切换阶段。

## 队友阵容与剩余卡池

展开游戏的队友总览，识别到三至四行密集阵容头像时会自动记录。「面板1–4」代表当前总览从上到下的行，避免靠玩家昵称猜身份。单人详情有清晰姓名时，也可选择对应行点击「从当前队友面板读取」。重复识别同一玩家会覆盖快照，商店里待售的卡不计入持有量。

头像无法确认晋级等级时，只记录一份占用下限。在「BAN与共享池 → 队友阵容 / 共享卡池」选择干员，可校正此人的普通、精锐、星级待确认数量，也可补录备战区。手动校正会保留到清除此人或新一局，不被后续头像扫描冲掉。

当前采用的估算口径：普通1份、精锐3份，星极精锐暂按2份；依据三合一规则和旧版共享池实测。当前「规程」各阶总池量及池外赠送牌如何回池尚未得到可靠核实，程序默认显示「总池待核实」，不套用旧版固定总数。设置总池量后显示 `0–(总量−记录占用下限)` 的估算范围；未见备战区、赠送来源、售出和记录时差均可能影响结果。30秒未刷新时提示快照过期。队友行顺序变化时应清除旧行记录重新扫描。该功能不是精确的服务器记牌器。

机制参考：[旧版共享卡池实测视频](https://www.bilibili.com/video/BV1JWy3BkEpt/)、[本期官方机制演示（队友总览）](https://www.bilibili.com/video/BV18RHN64EZV?p=2)、[本期客户端公开数据](https://github.com/Kengxxiao/ArknightsGameData/blob/master/zh_CN/gamedata/excel/activity_table.json)。新增攻略参考：[白樱规程通用叠层与经济卡](https://www.bilibili.com/video/BV1ZBW46eEdW/)、[伊比利亚分支思路](https://www.bilibili.com/video/BV1k1WW6AEx7/)、[阿戈尔实战](https://www.bilibili.com/video/BV1FnWn6XEA5/)。

## 从源码运行

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

离线诊断单帧，默认自动判断场景。`--scene` 可指定 `调度中心`、`盟约选择`、`策略轮选`、`自选编队`、`装备选择` 或 `队友阵容`。
`--output result.json` 将诊断结果保存到文件，免安装版本也可使用。

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --inspect screenshot.png
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

打包需要先安装 `pyinstaller==6.22.3`，再在仓库根目录执行 `build.ps1`。构建环境的第三方声明可用 `python tools/collect_notices.py` 更新，发布时将根目录许可和 `licenses/` 一并提供。MaaFramework 的替换库方法与源码见 [第三方说明](THIRD_PARTY_NOTICES.md)。

本地设置、导入的攻略及运行日志在 `%LOCALAPPDATA%\StrongholdAssistant`，可用 `STRONGHOLD_STATE` 指定其他位置。公开仓库不包含个人配置、账号截图或原始录屏。

### 目录

```text
main.py                   GUI 与离线识别入口
stronghold/app.py         桌面界面、抓屏线程与状态展示
stronghold/ui.py          规程终端风格的矢量组件与导航
stronghold/vision.py      ROI OCR、场景与盟约识别
stronghold/portraits.py   禁用名单及队友头像匹配
stronghold/domain.py      本局状态、可用池、攻略排序与提醒
stronghold/stock.py       按玩家记录持有量与估算余量
stronghold/windows.py    Win32 窗口绑定和抓屏
stronghold/overlay.py    置顶、非激活、鼠标穿透浮层
stronghold/pc_input.py   MaaFramework 显式单步输入
data/                    本期图鉴、识别模板与攻略 JSON Schema
tests/                   规则、状态、攻略校验与输入保护测试
licenses/                上游许可证和第三方声明原文
```

0.3.1 已通过 35 项自动测试；新增测试覆盖整套卡牌 BAN、功能位替代、未知状态和缓存失效。PC 客户端的原有实机验证与打包回放范围在下方来源及 [更新记录](CHANGELOG.md) 中说明。复现规则测试无需个人截图。

## 参考代码与组件来源

本项目参考 MAA 的截图、ROI、模板识别和 PC 控制思路，使用 MAA 战斗图鉴中的简中名称作为字典；没有集成 MAA 主程序。实际单步输入调用的是 **MaaFramework**，应用的界面、本局状态、攻略整合和提醒逻辑在本仓库实现。

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

完整间接依赖、模型来源与哈希、素材版权、参考与实际集成的区别，见 **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)** 和 **[DEPENDENCIES.json](DEPENDENCIES.json)**。攻略原作者及链接保留在每套阵容的 `sources` 中，可在应用里打开。

## 许可

原创应用代码和原创项目文档采用 [MIT](LICENSE)。PRTS 衍生文字按上游声明保留 **CC BY-NC-SA 3.0**；游戏名称、头像、美术及商标归鹰角网络及相应权利人；攻略表达归原作者。模型、第三方组件、游戏素材和攻略不因本仓库公开而统一改为 MIT。

再分发体验包时保留第三方声明和许可证目录，具体内容见 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 资料

- 客户端识别设计参考 MAA 的截图、ROI 和图像模板工作流。项目使用 RapidOCR 的 PP-OCR 模型，自选编队识别使用 MAA 战斗图鉴的简中干员名称。 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) · [MAA 战斗图鉴](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/resource/battle_data.json) · [MaaFramework](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/en_us/1.1-QuickStarted.md) · [RapidOCR](https://github.com/RapidAI/RapidOCR)
- 序列 I 的规则与图鉴来自游戏说明和 PRTS。阵容阶段、策略建议及装备提示参考社区图鉴和各阵容的实战攻略，出处可在应用中打开。盟约和策略图标用于画面识别，游戏素材版权归其权利人。 [官方公告](https://ak.hypergryph.com/news/0787.html) · [PRTS 盟约记录](https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录) · [战场说明](https://prts.wiki/w/卫戍协议·规程/战场一览) · [SquadPool 阵容索引](https://squad-pool.com/arknights-pacts)
- 商店实战样本包含默认与定制终端主题。战前验证样本取自先行试玩和官方机制演示。 [阿戈尔实战](https://www.bilibili.com/video/BV1FnWn6XEA5/) · [炎国实战](https://www.bilibili.com/video/BV1BPWJ6yE3P/) · [先行试玩](https://www.bilibili.com/video/BV19P4w6aEk3/) · [前瞻演示](https://www.bilibili.com/video/BV18RHN64EZV?p=2)
