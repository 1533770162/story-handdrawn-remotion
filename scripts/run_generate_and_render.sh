#!/usr/bin/env bash
# name=scripts/run_generate_and_render.sh
# 一键生成并渲染脚本（免费 agnes 后端 / font 字幕模式）
# 用法：
#   ./scripts/run_generate_and_render.sh            # 直接执行默认流程
#   DRY_RUN=1 ./scripts/run_generate_and_render.sh # 只做 dry-run（不生图）
# 可选环境变量：
#   BACKEND (默认 agnes)
#   TEXT_MODE (默认 font)
#   CONCURRENCY (默认 1)
#   TITLE (默认 "她的选择")
#   STORY (默认 examples/story_zh.txt)
#   REMOTION_COMPOSITION (默认 src/index.ts 的 Part2，可根据项目修改)
#   APIZ_KEY (若使用付费后端时提供)

set -euo pipefail
IFS=$'\n\t'

# 默认配置
BACKEND=${BACKEND:-agnes}
TEXT_MODE=${TEXT_MODE:-font}
CONCURRENCY=${CONCURRENCY:-1}
TITLE=${TITLE:-"她的选择"}
STORY=${STORY:-examples/story_zh.txt}
DRY_RUN=${DRY_RUN:-0}
REMOTION_COMPOSITION=${REMOTION_COMPOSITION:-"Part2"}
REMOTION_ENTRY=${REMOTION_ENTRY:-"src/index.ts"}
OUT_VIDEO=${OUT_VIDEO:-"out/${TITLE}.mp4"}
SCALE=${SCALE:-0.5}
CRF=${CRF:-28}

echo "Starting pipeline with settings:"
echo "  BACKEND=$BACKEND"
echo "  TEXT_MODE=$TEXT_MODE"
echo "  CONCURRENCY=$CONCURRENCY"
echo "  TITLE=$TITLE"
echo "  STORY=$STORY"
echo "  DRY_RUN=$DRY_RUN"

echo "\n1) 检查所需命令"
command -v python >/dev/null 2>&1 || { echo >&2 "Python 未安装，请先安装 Python 3.x"; exit 1; }
command -v node >/dev/null 2>&1 || { echo >&2 "Node 未安装，请先安装 Node.js 和 npm"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo >&2 "ffmpeg 未安装，请先安装 ffmpeg"; exit 1; }

# 2) 安装依赖（JS/Python）
if [ -f package.json ]; then
  echo "安装 JS 依赖... (npm install)"
  npm install
fi

if [ -f requirements.txt ]; then
  echo "安装 Python 依赖... (pip install -r requirements.txt)"
  pip install -r requirements.txt
fi

# 3) 生成 prompts / 生图
GEN_CMD=(python scripts/gen_story_images.py "$STORY" --lang zh --title "$TITLE" --backend "$BACKEND" --text-mode "$TEXT_MODE")
# 添加并发参数（若脚本支持）
if [ "$CONCURRENCY" != "1" ]; then
  GEN_CMD+=(--concurrency "$CONCURRENCY")
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "\n=== DRY-RUN: 只输出 prompts，不调用后端生图 ==="
  "${GEN_CMD[@]}" --dry-run
  echo "DRY-RUN 完成。确认 prompts 后去掉 DRY_RUN=1 来执行正式生图。"
  exit 0
fi

# 若使用付费后端 apiz，检测是否有 KEY
if [ "$BACKEND" = "apiz" ] && [ -z "${APIZ_KEY:-}" ]; then
  echo "警告：你选择了 apiz 后端但未提供 APIZ_KEY。请设置环境变量 APIZ_KEY=你的_key 或改用 agnes。"
  exit 1
fi

echo "\n=== 开始正式生图 (调用后端: $BACKEND) ==="
"${GEN_CMD[@]}"

# 4) 检查生成结果（脚本通常会打印输出目录）
# 这里尝试查找常见 output 目录
if [ -d out ]; then
  echo "生成完成，查看 out/ 目录获取 master 素材。"
elif [ -d output ]; then
  echo "生成完成，查看 output/ 目录获取 master 素材。"
else
  echo "生成脚本运行结束，请查看脚本输出日志以确认生成文件位置。"
fi

# 5) （可选）生成 TTS 音频（如果项目提供相应脚本或 narration.yaml）
if [ -f narration.yaml ]; then
  echo "检测到 narration.yaml，尝试运行仓库中的 TTS 脚本（如果存在）"
  if [ -f scripts/gen_narration_audio.py ]; then
    python scripts/gen_narration_audio.py narration.yaml || echo "gen_narration_audio.py 运行失败或不存在，跳过。"
  else
    echo "注意：仓库没有标准 TTS 脚本，若需请手动利用 edge-tts 或其它工具生成音频并放入 audio/ 目录。"
  fi
fi

# 6) Remotion 渲染（请确认项目已能本地运行 Remotion）
# entry: REMOTION_ENTRY (默认 src/index.ts)，composition: REMOTION_COMPOSITION
if command -v npx >/dev/null 2>&1; then
  echo "\n=== 开始 Remotion 渲染: composition=$REMOTION_COMPOSITION -> $OUT_VIDEO ==="
  npx remotion render "$REMOTION_ENTRY" "$REMOTION_COMPOSITION" "$OUT_VIDEO" --scale=$SCALE --crf=$CRF --concurrency=1 --overwrite
  echo "渲染完成：$OUT_VIDEO"
else
  echo "未检测到 npx，跳过 Remotion 渲染。请手动运行: npx remotion render $REMOTION_ENTRY $REMOTION_COMPOSITION $OUT_VIDEO --scale=$SCALE --crf=$CRF --concurrency=1 --overwrite"
fi

echo "\n全部流程完成。若需要改用付费后端请设置 BACKEND=apiz 并导入 APIZ_KEY 环境变量。"
