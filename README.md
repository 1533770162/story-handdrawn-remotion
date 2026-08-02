# story-handdrawn-remotion

把一段中文故事文本变成 「手绘日记漫画风」竖屏视频。Remotion技术的视频SKill. 基于 Agnes Image +edge-tts 全免费视频制作方案。

核心方法论：**不是把一张漂亮图配文字朗读，而是把每句故事拆成「文字 → 黑白画稿 → 彩色插画」三阶段横向擦除揭示，让一句话被画出三次。**

## 工具链

- **图片**：agnes（Agnes Image 2.1 Flash，默认，当前免费） / apiz CLI（`fal-ai/nano-banana-2`，付费可选）
- **字幕**：默认 font 模式（MaShanZheng 字体，Remotion TextWipe 实时画） / image2 模式（仅 apiz 支持图片模型在画板上画手写体）
- **音频**：MiniMax T2A v2（默认 `female-shaonv`） / edge-tts（免费 fallback）
- **切层**：ffmpeg（master 切 text/bw/color 三层；font 模式下不切 text_image）
- **渲染**：Remotion 4.x（React 控横向擦除 + 翻书转场）

## 快速开始

## 安装

```bash
在workbuddy，codex, claude code，直接命令要求安装skill:https://github.com/liangdabiao/story-handdrawn-remotion
```



安装后，技能会在 workbuddy,Claude Code 、codex 中按学科关键词自动激活，也可手动调用。

例如： 利用 story-handdrawn-remotion skill 帮忙制作一个视频：  王安石变法的故事

---


## 后端生图API选择

| 后端 | 收费 | 中文手写体字幕 | 适用 |
|---|---|---|---|
| `--backend agnes`（默认） | 当前 $0/张 | 必须用 `--text-mode font`（agnes 不会画中文） | 默认免费全流程 |
| `--backend apiz` | 付费 | 可用 `--text-mode image2`（apiz 在画板上画手写体） | 老样板复用 / 想要图片模型真迹字幕 |

不显式传 `--text-mode` 时脚本按后端自动选：agnes → font，apiz → image2。
agnes key免费申请地址： https://agnes-ai.com/

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

## Demo视频演示

https://www.bilibili.com/video/BV1un3X6fEDk/?vd_source=86926e418c83af75f6850b5546388a79

## 感谢

https://linux.do 社区支持
https://github.com/gnipbao/story-to-handdrawn-video  技术参考