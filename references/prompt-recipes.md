# apiz nano-banana-2 Prompt 配方

> 这是给 `gen_story_images.py` 的 prompt 工程参考。脚本已经内置了完整 prompt，本文档解释每个字段为什么这么写。

## 一、style_lock（视觉风格锁，全文照抄，一个字不要改）

```
minimalist Chinese diary comic reconstructed from the supplied reference video,
pure white background, uneven black felt-tip pen outlines, naive wobbly proportions,
rough dense black crayon scribbles for dark areas, sparse props, abundant negative space,
selective muted wax-crayon color only, no realistic shading, no paper texture, no watermark
```

**为什么这么长**：每个短语锁一个视觉维度：
- `pure white background` → 锁底色（防止 apiz 加米黄/渐变）
- `uneven black felt-tip pen outlines` → 锁线条（记号笔粗细变化）
- `naive wobbly proportions` → 锁比例（业余感、不对称）
- `rough dense black crayon scribbles for dark areas` → 锁阴影（涂黑而非渐变）
- `sparse props, abundant negative space` → 锁密度（不要塞满）
- `selective muted wax-crayon color only` → 锁色彩（蜡笔感、低饱和）
- `no realistic shading, no paper texture, no watermark` → 三道禁止

## 二、character_lock（角色一致性约束）

### 写法模板

```
固定 [N] 位主角：
[角色 A]：年龄，发型/脸型，[上装颜色+款式]，[下装颜色+款式]，[鞋]；
[角色 B]：年龄，...

两人的脸型、发型、年龄、服装配色和身体比例在所有场景必须一致；
[特殊规则，如：母亲只允许以墙上小幅遗照出现，不得作为真人出场]。
```

### 示例（父子故事）

```
固定两位主角：父亲约35岁，短黑发，清瘦疲惫的脸，灰蓝色旧工装外套、白色内衫、
深灰长裤、黑布鞋；儿子7岁，圆脸、短黑发、身形小，赭黄色针织上衣、灰蓝长裤、
黑布鞋。两人的脸型、发型、年龄、服装配色和身体比例在所有场景必须一致；
母亲只允许以墙上小幅遗照出现，不得作为真人出场。
```

### Narrative Isolation 规则（必加）

每场 master prompt 末尾必须有这两句：

```
Narrative isolation: the character lock defines identities, not an automatic cast list.
Show only characters explicitly named in the current sentence or strictly required
for its immediate action. Never add family bystanders. Never show a future daughter,
rescued child, grandmother, father or any other supporting character before that
person is introduced by the narration. Do not carry any person, prop or setting
forward merely because it appeared in another scene.
```

**为什么必加**：apiz 会「脑补」前一场出现过的人到下一场，导致叙事穿帮（如父亲回忆时儿子在旁边）。这段约束强制 apiz 只画当前句明确提到的人。

### `--character-lock` CLI 参数

```bash
python gen_story_images.py story.txt \
  --character-lock "固定主角：小红，8岁女孩，圆脸，黑色齐刘海短发，红色棉袄、黑裤子、白球鞋；奶奶，60岁，灰白发盘髻，深蓝对襟褂子、灰裤、黑布鞋。两人比例跨场景一致。"
```

## 三、caption_panel 坐标规范（image2 模式）

```
Top copy panel (pixels y=0–510): pure white background.
Write ONLY this Simplified Chinese caption verbatim, preserving the explicit line breaks:
"<caption text with \n>"
Use thick casual black felt-tip handwriting, 1–3 lines only, generous 48-pixel
left/right margins, and a large readable letter size. Do not put any illustration
or decorative mark in this panel. Do not place text below y=510.
```

**坐标解释**：
- master 是 1024×1536（portrait）
- y=0–510：字幕区（高度 510px ≈ 33% 总高，可容纳 2-3 行大字）
- y=510–512：白色过渡带（极窄，2px）
- y=512–1536：插画区（1024×1024 正方形）

**为什么不能让 apiz 把字写到插画区**：字幕会被 ffmpeg crop 出来当 text_image 层，如果跑到插画区，crop 会切到插画的一部分。

**为什么字幕区给到 y=510（而不是 22% 标准比例的 y=342）**：nano-banana-2 的中文字号偏大，2 行字幕实际会画到 y=460-500。原来 y=342 的硬限会让第 2 行被切。提到 y=510 给足空间，TextWipe 容器同步加高到 420px。

## 四、illustration_panel 坐标规范

```
Illustration panel (pixels y=512–1536): use this exact lower 1024×1024 square
for the scene. Keep the upper 510-pixel copy panel completely free of any illustration.
```

`ffmpeg` 的 color 层 crop 公式 `crop=1024:1024:0:512` 完全对应这个坐标，**改一处必须同步改另一处**（gen_story_images.py 的 `split_master_into_layers` 函数）。

## 五、safe border 10% 硬规则

每场 master prompt 末尾必须有：

```
Reserve a clean white safe border of at least 10% on the left and right and 8% on
the top and bottom. Every figure, limb, prop, building edge, roof, tree branch,
rain stroke and motion mark must stay completely inside that safe border.
Scale the scene down when necessary; never let any visible mark touch or cross
a canvas edge.
```

**为什么**：Remotion 渲染时 `objectFit: 'contain'` 会保持图片完整不裁，但如果原图本身就贴边，contain 后会显得拥挤。safe border 强制 apiz 自己留白。

## 六、配色约束（蜡笔五色）

```
Color: selective muted wax-crayon color only: sage green, dusty blue, warm tan,
brick red and warm yellow. Keep hair, trousers and other dark areas as black
scribbles. Leave skin and most of the canvas pure white.
```

**五色限定**：
- 鼠尾草绿（sage green）
- 灰蓝（dusty blue）
- 暖棕（warm tan）
- 砖红（brick red）
- 暖黄（warm yellow）

**禁止色**：纯红、纯蓝、亮黄、荧光色、渐变色。这些会让画面失去日记漫画的克制感。

## 七、5 种典型场景示例

### 1. 室内日常

```
Narrative sentence: "他在厨房煮泡面。"
Scene direction: "A tired father standing at a kitchen counter, a pot on a small
gas stove, a packet of instant noodles on the counter, simple line art, sparse props."
```

### 2. 室外活动

```
Narrative sentence: "孩子们在公园里放风筝。"
Scene direction: "Two children running in a park, a kite flying high above,
sparse trees in the background, low horizon line, generous sky negative space."
```

### 3. 情绪特写（不画脸）

```
Narrative sentence: "他偷偷哭了。"
Scene direction: "A man's back from behind, shoulders hunched, head down,
a single small teardrop shape near his cheek area, no face visible, abundant
white negative space around him."
```

⚠️ 手绘日记风的情绪特写**不要画脸**——用背影/侧影/手部动作传达，比正脸特写更克制。

### 4. 时间跳跃（用道具承接）

```
Narrative sentence: "三年后，孩子上学了。"
Scene direction: "A school backpack hanging on a hook by the door, slightly bigger
than the one the child used to have, a small pair of shoes neatly placed underneath.
The father's hand reaches into frame from the right edge only."
```

⚠️ 时间跳跃**用道具变化暗示**，不要直接画"长大的孩子"——观众通过背包大小变化脑补。

### 5. 抽象概念（金句卡）

```
Narrative sentence: "爱是世界上最美味的东西。"
Scene direction: "A simple bowl of noodles in the center, a small heart shape
drawn above the steam, no characters, no other props, abundant white space."
```

## 八、character_reference prompt（00_character_reference.png）

```
Use case: illustration-story
Asset type: fixed protagonist character reference sheet for a hand-drawn Chinese
diary-comic video

Input images: the supplied black-and-white and color frames are style references
only. Ignore their people, composition and Chinese text.

Primary request: draw ONLY the recurring protagonists described below. Show each
protagonist in two simple full-body poses, front view and three-quarter view,
arranged side by side.

Character lock: <你的 character_lock>
Style: <style_lock>
Composition: pure white square canvas, all uncropped full-body poses centered
with generous spacing and a clean 10% safe border. No scenery, furniture, extra
people, props or decorative marks.

Color: selective muted wax-crayon color only. Follow the clothing colors in the
character lock, use black scribbles for hair and dark trousers, and leave skin
and most of the canvas white.

Constraints: this is an identity reference only; no text, letters, numbers,
labels, captions, speech bubbles, logo, signature or watermark; no realistic
shading, gradients or vector cleanliness.
```

**生成后**：apiz upload 到 CDN，所有后续 master 用 `image_url=<cdn_url>` 引用，nano-banana-2 自动进入图生图模式锁定身份。

## 九、调试 prompt 的方法

### dry-run 看 prompt 不生成图

```bash
python gen_story_images.py examples/story.txt --title "..." --dry-run
```

会打印每场的完整 prompt 到 stdout，并写入 `prompts/<asset_set>/NN_master.txt`。

### 单场重新生成

```bash
# 删掉那场的 master
rm public/assets/generated/<asset_set>/03_master.png

# 重跑（脚本会跳过已存在的，只生成缺失的）
python gen_story_images.py examples/story.txt --title "..."
```

### 全部重新生成

```bash
python gen_story_images.py examples/story.txt --title "..." --force
```

⚠️ `--force` 会重新调 apiz 花钱，确认 prompt 改对了再用。

## 十、常见 prompt 问题排查

| 现象 | 原因 | 修复 |
|---|---|---|
| 主角脸不一样 | 没用 character_reference | 不要 `--no-character-ref` |
| 提到父亲时奶奶也在 | narrative isolation 没生效 | 检查 prompt 末尾的 Narrative isolation 段是否完整 |
| 字幕跑到插画区 | caption_panel 坐标错 | 检查 master prompt 里 y=0–342 段是否完整 |
| 配色太鲜艳 | style_lock 没强制 | 检查"selective muted wax-crayon only" + 五色限定 |
| 人物头顶出画 | safe border 没生效 | 检查 prompt 末尾"safe border 10%"段是否完整 |
| 画风变精致 | 模型 fallback | 检查 apiz 是否真的用了 nano-banana-2（看 `.last_generate.json`） |
