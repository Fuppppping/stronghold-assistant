# 攻略 JSON 格式

在「阵容与攻略 → JSON 格式与模板」可以查看说明、复制完整示例和另存模板。修改模板后使用「导入攻略 JSON」。文件使用 UTF-8，顶层是一个对象，不能带注释或尾随逗号。程序自带 `guide.example.json`，结构见 `data/guide.schema.json`。

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | 非空字符串，必填 | 唯一 ID，不能与已有攻略重复 |
| `name` | 非空字符串，必填 | 阵容名称 |
| `targets` | 对象，必填 | 盟约名称到正整数人数的映射，如 `{"阿戈尔":6}` |
| `plan` | 字符串 | 游戏浮层常驻显示的攻略思路，建议 30–60 字 |
| `stages` | 非空对象数组，必填 | 每项含 `name`；可含 `timing`、`plan`、`core`、`operators` |
| `stages[].core` | 干员名称数组 | 本阶段核心干员 |
| `stages[].operators` | 干员名称数组 | 本阶段可选、过渡或替代干员 |
| `stacking` | 对象数组 | 每项含 `operator`、`role`，可含 `note` |
| `stacking[].role` | `core` 或 `available` | 核心叠层 / 可用叠层，独立于输出核心身份 |
| `stacking[].note` | 字符串 | 触发时间、站位、转职或激活条件；显示在浮层卡片提示和攻略详情 |
| `requirements` | 对象数组 | 关键功能位；每项含 `name`、非空 `operators` 候选数组及可选的 `minimum`（默认1） |
| `strategies` | 策略名称数组 | 越靠前越优先 |
| `equipment` | 对象 | 装备名称到提示文字的映射；界面勾选、屏蔽可覆盖 |
| `sources` | 对象数组 | 每项含 `label` 与 `url`（http/https），保留原攻略出处 |

干员、盟约、策略和装备使用本赛季图鉴中的简中全名。导入时检查名称、数组、文字类型及正整数目标，错误会显示原因。未提供 `stacking` 的旧攻略仍可使用普通核心干员提示；未提供 `plan` 时显示通用思路。

`requirements` 中每个功能位必须至少保留 `minimum` 名未禁用候选；不足时整套阵容降级。候选尚未确认时会标为待确认。候选表示同一功能的备选方案，不保证效果或强度相同。未填写该字段的旧攻略按阶段核心推算最低覆盖，仍会按每张卡的可用性评分。

下面是最小示例；完整版本见 `guide.example.json`：

```json
{
  "id": "my-iberia",
  "name": "我的伊比利亚",
  "targets": {"伊比利亚": 6},
  "plan": "先用旅骨与低阶本家过渡，再按来牌选择精奥或迅捷。",
  "stages": [{"name": "前期", "core": ["旅骨"], "operators": ["深靛", "蓝毒"]}],
  "requirements": [{"name": "前期叠层", "operators": ["旅骨", "深靛"], "minimum": 1}],
  "stacking": [
    {"operator": "旅骨", "role": "core", "note": "休整末；关注身前站位与售价"},
    {"operator": "深靛", "role": "available", "note": "本家激活后在休整末叠层"}
  ],
  "strategies": ["变形同构"],
  "equipment": {"伊比利亚骨刺刀": "补本家人数"}
}
```
