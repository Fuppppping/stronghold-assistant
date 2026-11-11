# 卫戍协议助手

面向 Windows 的《明日方舟》卫戍协议·规程（序列 I）桌面助手。程序读取游戏画面，在前台游戏窗口上方显示鼠标穿透标记。数据和 OCR 模型随 Windows 版本提供，识别在本机运行。

## 开始使用

1. 打开 `StrongholdAssistant.exe`，再打开简中《明日方舟》或承载游戏的模拟器。助手会寻找客户端窗口。若识别到多个实例，可在下拉框手动绑定。
2. 进入卫戍协议的「确认本局信息」。助手读取亮起与置灰的盟约，并在「盟约与可用池」按羁绊显示干员。个人模拟的二选一会列出两组，向下滚动可补读附加盟约。双击盟约可校正状态。「仅显示已确认」筛选已确认可用的干员，本局商店实际出现过的干员标为「本局已见」。
3. 在「阵容与攻略」选定阵容。轮选策略时，浮层优先标记当前可见的攻略策略；未选阵容时会根据可用池推荐当前可见的选项。调度中心展开后，匹配的核心干员、过渡干员和装备会在对应卡片上方标记。
4. 在「装备提示」选择装备后点击「勾选提醒」「屏蔽」或「跟随攻略」。勾选和屏蔽会保留到下一次启动，屏蔽优先。未选阵容时也可以勾选装备。
5. 开局第一帧有效盟约结果即推算禁用干员，完整姓名在「BAN与共享池 → 本局 BAN 名单」。向下滚动游戏禁用名单会合并补读文字和标准头像，分别标注「盟约推算」「名单识别」。无法确认的干员保持待确认。
6. 重开回到「确认本局信息」时自动清空上一局的盟约、禁用名单、已见卡与队友持有量。连续两帧难度开始页/结束页也会清空；再次查看本局信息或滚动页面不会清空。手动重置按钮保留用于识别失败时校正，装备偏好与选定攻略继续保留。

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

离线诊断单帧，默认自动判断场景。`--scene` 可指定 `调度中心`、`盟约选择`、`策略轮选`、`自选编队` 或 `装备选择`。
`--output result.json` 将诊断结果保存到文件，免安装版本也可使用。

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py --inspect screenshot.png
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

打包需要先安装 `pyinstaller==6.22.3`，再在仓库根目录执行 `build.ps1`。本地设置、导入的攻略及运行日志在 `%LOCALAPPDATA%\StrongholdAssistant`，可用 `STRONGHOLD_STATE` 指定其他位置。

## 资料

- 客户端识别设计参考 MAA 的截图、ROI 和图像模板工作流。项目使用 RapidOCR 的 PP-OCR 模型，自选编队识别使用 MAA 战斗图鉴的简中干员名称。 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) · [MAA 战斗图鉴](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/resource/battle_data.json) · [MaaFramework](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/en_us/1.1-QuickStarted.md) · [RapidOCR](https://github.com/RapidAI/RapidOCR)
- 序列 I 的规则与图鉴来自游戏说明和 PRTS。阵容阶段、策略建议及装备提示参考社区图鉴和各阵容的实战攻略，出处可在应用中打开。盟约和策略图标用于画面识别，游戏素材版权归其权利人。 [官方公告](https://ak.hypergryph.com/news/0787.html) · [PRTS 盟约记录](https://prts.wiki/w/卫戍协议·规程/PRTS盟约记录) · [战场说明](https://prts.wiki/w/卫戍协议·规程/战场一览) · [SquadPool 阵容索引](https://squad-pool.com/arknights-pacts)
- 商店实战样本包含默认与定制终端主题。战前验证样本取自先行试玩和官方机制演示。 [阿戈尔实战](https://www.bilibili.com/video/BV1FnWn6XEA5/) · [炎国实战](https://www.bilibili.com/video/BV1BPWJ6yE3P/) · [先行试玩](https://www.bilibili.com/video/BV19P4w6aEk3/) · [前瞻演示](https://www.bilibili.com/video/BV18RHN64EZV?p=2)
