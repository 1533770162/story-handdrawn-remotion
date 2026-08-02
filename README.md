# story-handdrawn-remotion

把一段中文故事文本变成 1080×1440 的「手绘日记漫画风」竖屏视频。

核心方法论：**不是把一张漂亮图配文字朗读，而是把每句故事拆成「文字 → 黑白画稿 → 彩色插画」三阶段横向擦除揭示，让一句话被画出三次。**

## 工具链

- **图片**：apiz CLI（`fal-ai/nano-banana-2`，portrait_4_3）
- **音频**：MiniMax T2A v2（默认 `female-shaonv`）/ edge-tts（免费 fallback）
- **切层**：ffmpeg（master 切 text/bw/color 三层）
- **渲染**：Remotion 4.x（React 控横向擦除 + 翻书转场）

## 快速开始

```bash
cd <VIDEO_WORKSPACE>
mkdir my-story && cd my-story

# 1. 拷贝模板工程
cp -R "<skill_path>/templates/remotion-project/" ./
npm install   # 用原生 npm，不要 rtk npm

# 2. 写故事到 examples/story.txt（一句一拍，≤36 字）

# 3. 生成图片 + 切三层
python ../scripts/gen_story_images.py examples/story.txt \
  --title "我的故事" \
  --character-lock "固定主角：……"

# 4. 写 narration.yaml（每场 id + text = narration 字段）

# 5. 生成 MiniMax 旁白
python ../scripts/gen_tts.py narration.yaml --out-dir public/audio/narration

# 6. 回写 duration_sec
python ../scripts/apply_timeline.py

# 7. 预览
npm run dev                # Remotion Studio
npm run render:preview     # → out/picture_silent-preview.mp4

# ⚠️ 必须等用户确认后才进最终渲染
npm run render             # → out/picture_silent.mp4
```

## 输入模式

| 模式 | 适合 | 入口脚本 |
|---|---|---|
| 故事文本（默认） | 中文故事、日记、绘本 | `gen_story_images.py` |
| 上传图片 | 已有手绘扫描件 | `import_uploaded_pages.mjs` |

## 转场

- `--transition cut`（默认，硬切）
- `--transition page-flip --transition-sec 0.7`（右下角卷页）

## 文档导航

- 完整 pipeline：`references/pipeline.md`
- Remotion 组件 API：`references/components.md`
- apiz prompt 配方：`references/prompt-recipes.md`
- 守护文档（触发条件、风格 DNA、验收清单）：`SKILL.md`

## 免责

- apiz 余额不足时无法 fallback（不像 TTS 有直连兜底）
- 不要同时跑多个 `remotion render`（Windows temp 竞争会让音频混合失败）
- Chrome Headless Shell 国内下载慢，`remotion.config.ts` 已配系统 Chrome
