---
name: story-handdrawn-remotion
description: 用 Remotion 制作「手绘日记漫画风」故事视频：白底 + 黑色记号笔轮廓 + 蜡笔色，每句故事被画三次（文字→黑白画稿→彩色插画）横向擦除揭示，可选右下角卷页翻书转场，默认 MiniMax 旁白。当用户要把一段中文故事文案、生活日记、儿童绘本、教学小品变成竖屏手绘风视频，或把一组有序的手绘图片变成翻书动画时，必须使用这个 skill。触发词：手绘日记视频、日记漫画、故事变视频、手写字幕、擦除揭示、翻书效果、蜡笔色、paper diary comic、手绘故事、3:4 竖屏故事。
---

# Story Handdrawn Remotion（手绘日记风故事视频）

把一段中文故事文本（或一组有序的手绘图片）变成 3:4 竖屏（1080×1440）的手绘日记漫画动画。核心方法论：**不是把一张漂亮图配文字朗读，而是把每句故事拆成「文字 → 黑白画稿 → 彩色插画」三阶段横向擦除揭示，让一句话被画出三次。**

这套方法适合任何「生活叙事」类内容：日记、童话、亲情故事、教学小品、产品步骤插画。只要画面能拆成"独立的一句一画"，就能用这套流程制作。

**工具链**：agnes（Agnes Image 2.1 Flash，默认且当前免费） / apiz CLI（`fal-ai/nano-banana-2`，付费可选）+ ffmpeg（master 切三层 + caption 自动检测）+ MiniMax T2A v2（默认旁白） / edge-tts（免费可选）+ Remotion（React 控揭示/翻页/渲染）。

**质量原则（70% 即交付）**：单张 master 图达到 70% 标准就直接进下一阶段，不要逐场修污染、不要全量重画、不要写 `_fix_pollution` 脚本。配旁白、字幕、擦除动画后整体观感合格即可。目标是几小时内出片，不是每张图都完美。

**默认纯文生图**：`gen_story_images.py` 默认**不生成** character_reference、不使用图生图（实测 character_reference 会被 agnes 当成「角色立绘贴纸」污染每场）。只有用户显式要求角色锁或提供参考图时，才加 `--character-ref`（自动生成 00）或 `--character-ref-image <path>`（用用户提供的图）。

**preview 即成片**：`npm run render:preview`（720×960）产出的 MP4 就是默认交付物。**不要自动跑 `npm run render`（1080×1440）**，除非用户明确说"要高清 / 要 1080p / 要最终版"。1080p 渲染耗时长，preview 在手机/电脑上看已经足够。

**规范样板**：
- `<VIDEO_WORKSPACE>/handdrawn-story-ep01/` — 第一集成品工程（apiz + image2）
- `<VIDEO_WORKSPACE>/yueyanglou-ji/` — agnes + font 模式，免费全流程

遇到排版、节奏、prompt 拿不准的时候，先看它们的 `storyboard.json` 和 `prompts/` 下的 master prompt 留底。

**配套参考**：
- 完整 pipeline（三输入 + 双转场 + 三层切分 + 配音回写）：`references/pipeline.md`
- Remotion 组件 API 速查：`references/components.md`
- apiz nano-banana-2 prompt 配方：`references/prompt-recipes.md`（character_lock + caption_panel + safe border 等硬规则）

## 新一集工作流（11 步）

按以下顺序执行，每步完成再做下一步。

### 1. 读故事 + 列 beat checklist

读用户给的故事文本（粘贴的或 `story.txt` 文件）。先**列 beat checklist**：每段的关键动作、因果转折、道具、笑点、金句、结尾钩子。后续改写时用这张表防止把故事压成提纲。

例：故事「世上最美味的泡面」
- [ ] 单亲爸爸带 7 岁孩子
- [ ] 出差，匆匆关门
- [ ] 路上担心，反复打电话
- [ ] 孩子说"我很好"
- [ ] 提前回家，孩子已睡
- [ ] 发现被子下的泡面 → 怒火
- [ ] 第一次打孩子
- [ ] 孩子解释：给爸爸留的晚餐
- [ ] 真相：另一碗塞被窝保温
- [ ] 抱住孩子，金句

### 2. 写 story.txt（一句一拍，硬规则）

把故事保存为 UTF-8 文本。`gen_story_images.py` 内部的 `splitStory` 会按 `。！？；` 自动切句，超长句按 `，、` 和叙事转折词（后来/然后/突然…）再切。

**硬规则**：
- 单句 ≤ 36 字（softLimit），超长自动切但可能切坏节奏
- 自然段用空行分隔
- 一句一拍 = 一个 master = 一个画面

详见下方「故事忠实度」。

### 3. 视觉规划（可选但强烈推荐）

如果故事里有：
- 时间跳跃（"三年后"、"第二天"）
- 代词指代不明（"他"指的是谁？）
- 医疗场景（打针/手术）
- 年龄敏感角色（孩子长大、老人回忆）
- **任何题材都可能触发训练先验污染**（用户多次实测：家庭/医疗/商务/童话/历史都中过）→ 必读 `references/prompt-recipes.md` 第十一节，预规划 sanitized 文案 + CLOSE-UP 构图

→ 写 `visual_plan.json`，每场指定一个明确的视觉方向：

```json
{
  "01": "A tired father sitting alone at a kitchen table, head in hands, sparse props.",
  "07": "A man's back from behind, hand raised, a child's silhouette cowering, NO face visible on either."
}
```

用法：
```bash
python scripts/gen_story_images.py story.txt --visual-plan visual_plan.json
```

### 4. 脚手架

```bash
mkdir "<VIDEO_WORKSPACE>/<项目名>"
cp -R "./skills/story-handdrawn-remotion/templates/remotion-project/" \
      "<VIDEO_WORKSPACE>/<项目名>/"
cd "<VIDEO_WORKSPACE>/<项目名>" && npm install
```

⚠️ 用原生 `npm install`，不要 `rtk npm install`（rtk 会翻译成 `npm run install` 报错）。

模板自带的目录：
- `public/fonts/` — MaShanZheng 毛笔字体（OFL 协议）
- `public/audio/narration/` — TTS 产出占位
- `public/assets/generated/` — apiz 产出的 master 占位
- `references/style-bw.png` + `style-color.png` — 风格锚点参考图（**必备**，缺了脚本会 hard fail）

### 5. 选输入模式 + 选后端 + 选转场

| 输入 | 命令 |
|---|---|
| 故事文本（默认） | `python scripts/gen_story_images.py examples/story.txt --title "..."` |
| 上传图片 | `node scripts/import_uploaded_pages.mjs --image 01.jpg --image 02.jpg --title "..."` |

后端选项（`--backend`）：
- `agnes`（默认，Agnes Image 2.1 Flash，当前 $0/张免费，高密度中文手绘风）
- `apiz`（fal-ai/nano-banana-2，付费，老样板用这个）

字幕渲染（`--text-mode`，**未传时按后端自动选**）：
- `agnes` 后端 → 自动用 `font`（MaShanZheng 字体，agnes 不会画中文汉字）
- `apiz` 后端 → 自动用 `image2`（apiz 在画板上画手写体）

转场选项：
- `--transition cut`（默认，硬切）
- `--transition page-flip --transition-sec 0.7`（右下角卷页，0.5–2.0 秒）

### 6. 生成 master + 切三层（gen_story_images.py）

```bash
python scripts/gen_story_images.py examples/story.txt \
  --title "世上最美味的泡面" \
  --visual-plan visual_plan.json \
  --transition cut
# --backend 默认 agnes，--text-mode 默认按后端自动选（agnes→font / apiz→image2）
# 默认纯文生图，不生成 character_reference（避免角色立绘污染）
```

需要角色锁时（用户明确要求或提供了参考图）才加：
```bash
# 自动生成 00_character_reference.png 并走图生图
python scripts/gen_story_images.py story.txt --character-ref
# 或用用户提供的参考图
python scripts/gen_story_images.py story.txt --character-ref-image ./my-ref.png
```

脚本流程：
1. 校验 `references/style-bw.png` + `style-color.png` 存在
2. 分句 + formatCaption + durationFor 估时
3. 默认纯文生图（无 character_reference）；只有加 `--character-ref` / `--character-ref-image` 才生成/使用角色参考
4. 每句生成 master
5. ffmpeg 切三层：text_image / bw / color（font 模式下 text_image 不切，由 Remotion TextWipe 实时渲染字幕）
6. 写 `storyboard.json`（含 `narration` 字段供 TTS 用）

**dry-run 先看 prompt**：
```bash
python scripts/gen_story_images.py examples/story.txt --title "..." --dry-run
```

**切后端到 apiz**（仅当 agnes 不可用或要复用老样板）：
```bash
python scripts/gen_story_images.py examples/story.txt --backend apiz --text-mode image2
```

### 7. 生成旁白（gen_tts.py，默认 MiniMax）

`narration.yaml` 从 `storyboard.json` 转换（id + text = narration 字段，**不是 caption 字段**）：

```yaml
voice: female-shaonv
speed: 1.0
scenes:
  - id: s01
    text: "他是个单亲爸爸，独自带着一个七岁的孩子。妻子走后，家里就只剩他们两个人了。"
  - id: s02
    text: "..."
```

跑 MiniMax（默认）：
```bash
python scripts/gen_tts.py narration.yaml --out-dir public/audio/narration
```

跑 edge-tts（免费 fallback，用户明说"用免费的"或 MiniMax 配额耗尽）：
```bash
python scripts/gen_tts.py narration.yaml --backend edge --out-dir public/audio/narration
# voice 自动切 zh-CN-XiaoyiNeural（女声）；可在 yaml 显式指定其他 voice
```

⚠️ **edge-tts 命名陷阱**：edge 输出 `1.mp3 2.mp3 ...`（无前导 0），timeline.json 的 id 是 int（1/2/3...），而 storyboard 期望 `sXX.mp3` + string id。必须跑一个修复脚本：rename 成 `sXX.mp3` 格式 + 重写 timeline ids 为零填充 string + 把 storyboard 的 narration_audio 改成 `/audio/narration/sXX.mp3`。参考 `yueyanglou-ji/_fix_audio.py`。MiniMax 不踩这个坑。

产出 `s01.mp3 s02.mp3 ...` + `timeline.json`（含 `frames_source` / `frames_playback`）。

### 8. 回写 duration_sec（apply_timeline.py）

```bash
python scripts/apply_timeline.py
# 默认用 frames_source（原速）。如需 1.2x 加速：--use-playback
```

会把 `storyboard.json` 每场的 `duration_sec` 改成音频真实时长，同时填 `narration_audio` 字段（让 Scene.tsx 能挂 `<Audio>`）。

### 9. 静态检查（Remotion Studio）

```bash
npm run dev
```

打开 Remotion Studio，重点检查：
- safe border 10% 是否守住（人物头顶/手肘/道具不出边）
- caption 不超 3 行
- character 一致性（同一个人的脸/服装跨场景一致）
- 横向揭示方向一致（text/bw/color 都从左到右）

### 10. 渲染 preview（720×960）= 默认成片

```bash
npm run render:preview
# → out/picture_silent-preview.mp4
```

**⚠️ `picture_silent-preview.mp4` 就是默认交付物**。走完 TTS + apply_timeline 后直接渲 preview，把它交给用户即可。**不要自动跑 1080p 最终渲染**。

只有用户明确说"要高清 / 要 1080p / 要最终版 / 出高清"时才进第 11 步。

### 11.（可选）1080p 高清版 — 仅在用户明确要求时

```bash
npm run render
# → out/picture_silent.mp4

ffprobe -v error -show_streams -show_format out/picture_silent.mp4
```

1080p 渲染 2000+ 帧耗时长，preview 在手机/电脑上看已经足够清晰，不要主动跑。

## 故事忠实度

- 原文是故事，**不是提纲**。改成 video 脚本时可以合并相近句子，但不能删关键桥段导致因果断裂。
- 保留"动作承接"和"道具承接"。开门、转身、拿出物品、合上书这类动作是观众理解下一句的桥。
- 旁白可以压短，但必须保留原文的情绪推进：压力来源 → 冲突 → 误解 → 揭示 → 金句/收尾。
- 单句 ≤ 36 字（`splitStory` 的 softLimit），超长自动切。**故事 txt 不要一句塞两句的内容**。
- 若必须删减，先列出将删的 beat，确认不是后文所需的连接段。
- TTS 前做一次对照：逐场检查 beat checklist，确认没有漏掉重要句子、动作、转折和金句。

## 风格 DNA（不可变）

| 项 | 值 |
|---|---|
| 画布 | 1080×1440 @ 30fps（3:4 竖屏），白底 `#FFFFFF` |
| 揭示 | text → bw → color，三层全部从左到右横向擦除（`inset(0 X% 0 0)`） |
| 转场 | cut 直接切（默认）/ page-flip 右下角卷页 |
| 墨色 | `#171714`，记号笔粗轮廓 + 蜡笔色块 |
| 字幕字体 | 站酷马善政毛笔（MaShanZheng），1.34 行高，-0.35° 倾斜 |
| 五色限定 | 鼠尾草绿 / 灰蓝 / 浅棕 / 砖红 / 暖黄（低饱和蜡笔色，禁止纯红/亮黄/荧光） |
| 素材 | agnes / apiz 生成真实 PNG，**不是**纯代码绘制 |
| 图片生成 | 默认 agnes（`agnes-image-2.1-flash`，免费，ratio 2:3，2K = 1664×2496 缩到 master 1024×1536）；可选 apiz（`fal-ai/nano-banana-2`，`image_size='portrait_4_3'`） |
| 字幕渲染 | 默认 font（MaShanZheng 字体，Remotion TextWipe 实时画） / image2（仅 apiz 支持图片模型画手写体，agnes 不会画中文） |
| 默认配音 | MiniMax T2A v2，`female-shaonv`（apiz speak `speech-2.8-hd` → 直连 `speech-02-hd` fallback） |
| 免费 fallback | edge-tts，`zh-CN-XiaoyiNeural`（女声），`pip install edge-tts` |
| 输出 | H.264 MP4，默认含旁白音轨 |
| safe border | 至少 10% 左右、8% 上下，所有笔触不触边 |

## 角色一致性（默认关闭）

**默认纯文生图**：不加 `--character-ref`，不生成 `00_character_reference.png`，不传图生图参考。视觉规划靠 `visual_plan.json` 里每句的构图描述 + `--character-lock` 里的服装规则。实测这样出片最快，70% 质量足够。

**需要角色锁时**（用户明确要求同一张脸跨场一致，或提供了参考图）：
```bash
# 自动生成 00 角色锚点
python scripts/gen_story_images.py story.txt --character-ref --character-lock "..."
# 或用用户提供的参考图
python scripts/gen_story_images.py story.txt --character-ref-image ./ref.png
```

`--character-lock` 写服装规则即可（年龄/服装颜色/标志道具），不要写长串负面禁止词——模型会被负面词触发反而画出你禁止的东西。

## 场景语法版式约定

### 1. 标题场景（两种模式）

**image2 模式**（仅 apiz 后端可用，需要图片模型在画板上画手写体字幕）：
- 上半 y=0–510：手写体字幕（apiz 在 master 上画，ffmpeg 切出 text_image 层）
- 下半 y=512–1536：彩色插画（1024×1024 正方形）
- y=510–512：极窄过渡带（2px，实际几乎不可见）
- 字幕区给到 510px 是因为 nano-banana-2 中文字号偏大，2-3 行字幕实际会画到 y=460-500

**font 模式**（agnes 默认，apiz 也可用）：
- 整张 master 1024×1536 全是彩色插画（agnes 不会画中文，所以不在画板上留字幕区）
- 字幕由 Remotion 用 MaShanZheng 毛笔字体实时渲染（`TextWipe` 组件）
- ffmpeg 不切 text_image 层（storyboard 的 `text_image=null`）
- 排版完全可控，不依赖图片模型识字

### 2. 完整页上传（full_uploaded_page）

- `<Img objectFit="contain">` 居中显示原页，绝不裁剪
- 用于 page-flip 模式：保留原页 + 卷页时露出淡化纹理

### 3. 复合页（composite）

- ffmpeg cropdetect 自动找空白带
- 上 caption + 下插画分别切出
- 失败时用 `--split-y 01:320` 手动指定像素行

### 4. 翻书效果（page-flip）

- 每场 Scene 静止显示后，右下角卷起 → 露出下一场
- 纸背保留淡化原页纹理
- 不要叠加 bw/color 阶段（保留原页即可）

### 5. 节奏（durationFor 公式）

```
duration_sec = min(6.2, max(4.4, 3.8 + line_count × 0.48 + char_count × 0.035))
```

- 1 行字幕 ≈ 4.4 秒
- 2 行字幕 ≈ 5.0 秒
- 3 行字幕 ≈ 5.5–6.2 秒
- 配音版会覆盖为真实音频时长

## 节奏（无配音版 + 配音版）

### 无配音版（估时，快速预览排版用）

`gen_story_images.py` 写入 `storyboard.json` 的 `duration_sec` 是估时（公式见上）。用于：
- 第一次跑预览看排版
- 验证场景顺序、转场、字幕布局

**不要停留在无配音版**——`audio.voiceover='pending'` 状态只是中间产物。

### 配音版（默认，必出）

走完 `gen_tts.py` + `apply_timeline.py` 后，`audio.voiceover='active'`，每场 `duration_sec` 是音频真实时长。

### 1.2x 加速（可选，不推荐）

教学/快节奏场景才用：
```bash
python apply_timeline.py --use-playback
# Scene.tsx 的 <Audio> 加 playbackRate={1.2}
```

手绘日记风重韵味，**默认原速**。

## 多音色配音流程（扩展位）

默认单旁白（narration 一个 voice）。如需多音色（旁白 + 角色台词）：

1. 在 narration.yaml 里给 utterance 加 `role` 字段
2. gen_tts.py 暂时按单 voice 处理（可手动改 voice 字段，分多次跑）
3. 未来可扩展支持 role → voice 映射表

详见 `references/pipeline.md` 第五节。

## 音画同步验收

生成配音后，**必须检查**音频、字幕、动画三者对齐：

- 视频总时长 ≈ 音频总时长，不能明显长出或短于
- 每场最后 30 帧不再出现新文字/插画（避免刚出现就切场）
- 抽查每场字幕：`TextWipe` 在 `startFrame=0` 出现，所以字幕一开始就在；插画 `bw` 在 0.18 总时长开始出。**字幕不能比音频晚**——字幕是先于"说到"出现的（视觉铺垫）
- 关键词级抽查：流程词/列表词/金句关键词，必须在音频说到那一句附近出现，不能提前十几帧露后面内容
- 每场最终截图过一次 Subagent 视觉审核：区分"叙事遮挡"vs"穿帮遮挡（人物脸被字盖住）"
- ffprobe 检查 mp4 video/audio duration 一致

详见 `references/pipeline.md` 第五节「配音回写机制」。

## 验收清单（渲染前必过）

技术项（必须过）：
- [ ] **句长合规**：每句 ≤ 36 字（超长会被 `splitLongBeat` 切坏）
- [ ] **caption 不超 3 行**：`formatCaption` 抛错前提前检查
- [ ] **narration_audio 已挂载**：每场 Scene 有 `<Audio>`，`audio.voiceover='active'`
- [ ] **duration_sec 已回写**：用 timeline.json 真实时长，不是估时
- [ ] **ffprobe 检查**：mp4 video/audio duration 一致

质量项（70% 即可，不要逐场修）：
- 故事连贯、字幕不截断、横向揭示方向一致
- 图片有污染/角色重复/构图不完美——**不阻塞出片**，配旁白和动画后整体能看就行
- 只有某张图严重到无法观看（全黑/全白/明显错内容）才重画那一张，不要全量重画

## 静帧查看策略（重要）

`remotion still` 渲出的静帧要肉眼检查排版，但默认放 `out/check-N.png` 在 Windows 下走 analyze_image MCP 会因路径反斜杠报 400。

```bash
# 1. 渲静帧到 out/
npx remotion still PictureSilent --frame=<场景末帧-30> out/check-s1.png

# 2. 缩成 jpg 并复制到 cwd 根目录
python -c "from PIL import Image; Image.open('out/check-s1.png').convert('RGB').save('_verify-s1.jpg', quality=85)"

# 3. Read 工具读 _verify-s1.jpg，拿到干净的 CDN URL 再传给 analyze_image
```

## 常见坑

- **rtk npm install 会失败**，用原生 `npm install`。
- **references/style-bw.png / style-color.png 缺失** → `gen_story_images.py` 启动时 hard fail。模板自带这两张图，不要删。
- **`--no-character-ref` 滥用** → 主角每场长出不同的脸。除非测试 prompt，否则永远不要用。
- **caption 超 3 行** → `formatCaption` 抛错。预先在 story.txt 把长句拆开（≤36 字）。
- **Chrome Headless Shell 国内下载卡**（113MB storage.googleapis.com）→ 模板的 `remotion.config.ts` 已配 Windows Chrome 路径，跳过下载。换机器若 Chrome 路径不同，改这个配置。
- **`--transition page-flip` 的 master 必须完整未裁剪** → 卷页会露出原页纹理，被裁过会穿帮。
- **复合页 cropdetect 失败** → 用 `--split-y 01:320` 手动指定 caption 与插画的分界像素行。
- **nano-banana-2 不支持 portrait_4_3** → fallback 到 `square_hd` + ffmpeg pad。`gen_story_images.py` 已用 portrait_4_3，若 apiz 报错，改 `image_size` 参数。
- **不要停留在无配音估时版**（`audio.voiceover='pending'`）——真实 TTS 生成后必须 `apply_timeline.py` 回写一版。
- **不要因为追求短而删故事连接段**——场数可增加（10→12→15），连贯性优先。
- **apiz 余额不足** → `apiz auth status` 检查；图片生成失败时无法 fallback（不像 TTS 有直连兜底），需充值或换模型。
- **MiniMax 配额耗尽** → `gen_tts.py --backend edge` 切免费 edge-tts（用户明说"用免费的"也用这个）。
- **音频混合失败（audio-mixing 目录缺失）** → 根因是并发渲染竞争 Windows temp。模板已设 `Config.setConcurrency(1)`。⚠️ **绝对不要同时跑多个 `remotion render`**。
- **第 2 行字幕被切** → 历史 bug：原来 `CAPTION_CROP_HEIGHT=342` 太小，nano-banana-2 中文字号偏大实际画到 y=460-500。已修：crop 高度 342→510、scale 1536:765、TextWipe 容器 height 288→420 / top 86→50、LayerWipe top 382→488。**4 处必须同步改**（`gen_story_images.py` 的 CAPTION_CROP_HEIGHT + scale + TextWipe.tsx 容器 + LayerWipe.tsx 容器）。如果只动 crop 不动容器，文字会被压扁。
- **agnes 不会画中文汉字** → agnes 后端必须用 `--text-mode font`（默认就是）。image2 模式下 agnes 会忽略"上方留白字幕区"指令把整张画布画满，导致字幕无处可放。脚本已自动按后端选默认值，但显式传 `--backend agnes --text-mode image2` 仍会踩坑。
- **agnes 上游 503 "Service busy" / 网络超时** → `lib_agnes.py` 自带 4 次指数退避（5/10/20/40s）。18 张图大概率要重试几次，正常现象。脚本对每场 master 自动 skip 已存在的，可反复重跑直到全 18 张完成。
- **Windows GBK subprocess UnicodeDecodeError** → 含中文路径（如 `public/assets/generated/岳阳楼记-xxx/`）下，ffmpeg stderr 被 Python 默认按 GBK 解码炸掉。脚本所有 subprocess.run 已加 `encoding="utf-8", errors="replace"`。改脚本时新加 subprocess 也要带这两个参数。
- **edge-tts 文件名/ID 陷阱** → `gen_tts.py --backend edge` 输出 `1.mp3`、`2.mp3`（无前导 0），`timeline.json` 的 id 是 int 1 而非 string "01"。`apply_timeline.py` 只能匹配 13-18 这种字符串/数字都相同的场景。修复：rename 成 `s01.mp3` 格式 + 重写 timeline ids 为零填充 string + 把 storyboard 的 narration_audio 改成 `/audio/narration/sXX.mp3`（参考 `yueyanglou-ji/_fix_audio.py`）。MiniMax 不踩这个坑（它用 `sXX.mp3`）。
- **agnes 2:3 ratio at 2K = 1664×2496** → 必须 `_normalize_master` 缩到 1024×1536（脚本已自带逻辑，但若改了 ratio 要重新算）。
- **训练先验污染** → agnes/apiz **任何题材**都可能从训练数据强塞刻板角色（不限历史；性别/种族/时代错位/场景标配都会发生，用户多次实测）。NEGATION suffix + character_lock 都压不住。修复走 **v3 玩法**：正向身份压过负向禁止（"ALL figures X" 比 "NO Y" 强）+ CLOSE-UP 构图 2-3 人上限（广角人群给模型塞人机会）+ sanitized text 替换触发词 + 纯文生图不用 character_reference（reference 本身被污染会 forward）。详见 `references/prompt-recipes.md` 第十一节。范例：`mayflower-story/_fix_pollution_v3.py`。修复后必须用 `analyze_image` MCP 并行验证所有场 CLEAN 才进 preview。
- **agnes HTTP 500 也要重试** → `lib_agnes.py` 已扩展重试白名单到 `(500, 502, 503, 504)`（之前只重试 502-504）。500 通常是上游 `do_request_failed` 瞬时错，5s 后重试就好。

## 适用范围

这套方法适合任何「一句一画」的叙事：

- 日记漫画 / 生活记录
- 童话 / 儿童绘本
- 亲情 / 情感故事
- 教学小品（步骤插画）
- 产品步骤演示（不重实物，重氛围）

**不适合**：
- 实物产品展示（用 product-launch-video）
- 真人/口播视频（用 talking-head-remotion）
- 微信公众号文章转视频（用 wechat-article-remotion）
- 纸片分层动画（用 paper-cutout-remotion）
- 数学/几何证明（用 geometry-math-proof-remotion）

真正让手绘日记风有韵味的，不是单张图多漂亮，而是「一句话被画出三次」的节奏 + 「文字先于声音出现」的视觉铺垫。
