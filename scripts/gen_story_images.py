"""gen_story_images.py — 故事文本 → apiz 生成 master → ffmpeg 切三层 → 写 storyboard.json

把 story-to-video.mjs 的核心逻辑（分句、prompt 模板、style_lock、character_lock）移植到
Python，把图像生成从 Codex Image2 / OpenAI API 改成 apiz CLI（默认 fal-ai/nano-banana-2）。

流程：
  1. splitStory：按 。！？； 切句，超长句按 ，、 和叙事转折词再切
  2. formatCaption：每句按 13 字/行 × 3 行格式化为字幕（含 \\n）
  3. 生成 character_reference（00_character_reference.png）
  4. 每句生成 master → apiz upload → 后续 master 用 image_url 引用保证一致性
  5. ffmpeg 切三层：text_image / bw / color
  6. 写 storyboard.json（含 narration 字段，供 gen_tts.py 用）

用法：
  python gen_story_images.py examples/story.txt --title "纸上的夏天"
  python gen_story_images.py examples/story.txt --title "..." --dry-run
  python gen_story_images.py examples/story.txt --title "..." --visual-plan plan.json
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_apiz import generate_image as apiz_generate_image, upload as apiz_upload, DEFAULT_IMAGE_MODEL  # noqa: E402
from lib_agnes import generate_image as agnes_generate_image, DEFAULT_MODEL as AGNES_DEFAULT_MODEL  # noqa: E402

DEFAULT_BACKEND = "agnes"

# ============================================================================
# 风格锁定字符串（直接照抄 story-to-video.mjs）
# ============================================================================

STYLE_LOCK = (
    "minimalist Chinese diary comic reconstructed from the supplied reference video, "
    "pure white background, uneven black felt-tip pen outlines, naive wobbly proportions, "
    "rough dense black crayon scribbles for dark areas, sparse props, abundant negative space, "
    "selective muted wax-crayon color only, no realistic shading, no paper texture, no watermark"
)

DEFAULT_CHARACTER_LOCK = (
    "重复出现的主角须保持同一张脸、发型、年龄、服装配色和身体比例；"
    "具体人物身份以故事原文为准；不得添加原文未提及的配角、道具或文字"
)

# ============================================================================
# 分句算法（直接照抄 story-to-video.mjs 的 splitStory / splitLongBeat / formatCaption）
# ============================================================================

TERMINAL_PUNCT = re.compile(r"[。！？!?；;]$")
NARRATIVE_TURN = re.compile(
    r"^(后来|然后|接着|突然|可是|但是|但|却|于是|直到|最后|没想到|第二天|那天|这时)"
)


def hard_chunk(value: str, max_length: int = 36) -> list[str]:
    chunks = []
    remaining = value.strip()
    while len(remaining) > max_length:
        window = remaining[: max_length + 1]
        cut = max(window.rfind("，"), window.rfind("、"), window.rfind("；"))
        if cut < max_length * 0.55:
            cut = max_length
        else:
            cut += 1
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def split_long_beat(sentence: str, soft_limit: int = 36) -> list[str]:
    value = sentence.strip()
    if len(value) <= soft_limit:
        return [value]

    m = TERMINAL_PUNCT.search(value)
    ending = m.group(0) if m else ""
    body = value[: -len(ending)] if ending else value

    clauses = re.split(
        r"(?<=，|、)|(?=(?:后来|然后|接着|突然|可是|但是|但|却|于是|直到|最后|没想到|第二天|那天|这时))",
        body,
    )
    clauses = [c.strip() for c in clauses if c.strip()]
    if len(clauses) == 1:
        return hard_chunk(value, soft_limit)

    beats = []
    current = ""
    for clause in clauses:
        candidate = f"{current}{clause}"
        starts_new_beat = bool(NARRATIVE_TURN.match(clause)) and len(current) >= 12
        if current and (len(candidate) > soft_limit or starts_new_beat):
            beats.append(re.sub(r"[，、]$", "。", current))
            current = clause
        else:
            current = candidate
    if current:
        beats.append(f"{re.sub(r'[，、]$', '', current)}{ending or '。'}")
    return [b for beat in beats for b in hard_chunk(beat, soft_limit)]


def split_story(text: str) -> list[str]:
    normalized = re.sub(r"\r", "", re.sub(r"[ \t]+", " ", text)).strip()
    paragraphs = [p.strip() for p in re.split(r"\n+", normalized) if p.strip()]
    beats: list[str] = []
    for para in paragraphs:
        sentences = re.findall(r"[^。！？!?；;]+[。！？!?；;]?", para)
        for sent in sentences:
            beats.extend(split_long_beat(sent))
    return [
        (b if TERMINAL_PUNCT.search(b) else f"{b}。")
        for b in map(str.strip, beats)
        if b
    ]


def format_caption(text: str, max_chars_per_line: int = 13, max_lines: int = 3) -> str:
    lines = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= max_chars_per_line:
            lines.append(remaining)
            break
        window = remaining[: max_chars_per_line + 1]
        cut = max(window.rfind("，"), window.rfind("、"), window.rfind("；"), window.rfind("："))
        if cut < max_chars_per_line * 0.45:
            cut = max_chars_per_line
        else:
            cut += 1
        lines.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
        if remaining and re.match(r"^[。！？!?；;：:,，、]", remaining):
            lines[-1] += remaining[0]
            remaining = remaining[1:].strip()
    if len(lines) > max_lines:
        raise ValueError(
            f"Caption needs {len(lines)} lines (> {max_lines}); split story beat before rendering"
        )
    return "\n".join(lines)


def duration_for(caption: str) -> float:
    line_count = caption.count("\n") + 1
    char_count = len(caption.replace("\n", ""))
    return round(min(6.2, max(4.4, 3.8 + line_count * 0.48 + char_count * 0.035)), 1)


# ============================================================================
# apiz upload + 切三层（移植 import-codex-images.mjs 的 ffmpeg filter）
# ============================================================================

CAPTION_CROP_HEIGHT = 510
CAPTION_SCAN_HEIGHT = 600


def detect_caption_crop_y(master_path: Path, project_root: Path) -> int:
    """用 ffmpeg cropdetect 自动检测 caption 区域。失败时返回 0（top-aligned）。"""
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "verbose",
            "-loop", "1", "-i", str(master_path),
            "-vf",
            f"crop=1024:{CAPTION_SCAN_HEIGHT}:0:0,negate,format=gray,"
            f"lut=y='if(gt(val,80),255,0)',cropdetect=limit=0.1:round=2:reset=0",
            "-frames:v", "3", "-f", "null", "-",
        ],
        cwd=project_root, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    log = f"{proc.stdout}\n{proc.stderr}"
    matches = list(re.finditer(r"crop=(\d+):(\d+):(\d+):(\d+)", log))
    if proc.returncode != 0 or not matches:
        print(f"  ⚠️ caption bounds 检测失败: {master_path.name}，用 top-aligned")
        return 0
    last = matches[-1]
    content_h = int(last.group(2))
    content_y = int(last.group(4))
    centered = round(content_y + content_h / 2 - CAPTION_CROP_HEIGHT / 2)
    return max(0, min(CAPTION_SCAN_HEIGHT - CAPTION_CROP_HEIGHT, centered))


def ffmpeg_run(input_path: Path, vf: str, output: Path, project_root: Path) -> None:
    """跑 ffmpeg 单帧切图（用于 master → text/bw/color）。"""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-vf", vf, "-frames:v", "1", "-y", str(output),
        ],
        cwd=project_root, check=True,
        encoding="utf-8", errors="replace",
    )


def _probe_size(path: Path) -> tuple[int, int]:
    """读图片宽高。失败返回 (0, 0)。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             str(path)],
            capture_output=True, text=True, check=True,
            encoding="utf-8", errors="replace",
        )
        w, h = out.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 0, 0


def _normalize_master(master_path: Path, project_root: Path, text_mode_image2: bool) -> Path:
    """nano-banana-2 有时返回 416×624 而非 1024×1536；先 in-place upscale 到目标尺寸。

    text_mode_image2=True 目标 1024×1536，False 目标 1024×1024。
    若尺寸已正确，直接返回原路径。
    """
    target_w, target_h = (1024, 1536) if text_mode_image2 else (1024, 1024)
    w, h = _probe_size(master_path)
    if w == target_w and h == target_h:
        return master_path
    if w == 0 or h == 0:
        return master_path  # 探测失败，让下游 ffmpeg 自己报错
    tmp = master_path.with_suffix(".normalized.png")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-i", str(master_path),
         "-vf", f"scale={target_w}:{target_h}:flags=lanczos",
         "-frames:v", "1", "-y", str(tmp)],
        cwd=project_root, check=True,
        encoding="utf-8", errors="replace",
    )
    tmp.replace(master_path)
    print(f"  ↑ master normalized {w}×{h} → {target_w}×{target_h}")
    return master_path


def split_master_into_layers(
    master_path: Path,
    asset_dir: Path,
    scene_id: str,
    project_root: Path,
    text_mode_image2: bool,
) -> dict[str, str]:
    """把一张 master 切成 text/bw/color 三层。返回相对路径（用于 storyboard）。"""
    _normalize_master(master_path, project_root, text_mode_image2)
    text_path = asset_dir / f"{scene_id}_text.png"
    bw_path = asset_dir / f"{scene_id}_bw.png"
    color_path = asset_dir / f"{scene_id}_color.png"

    if text_mode_image2:
        caption_y = detect_caption_crop_y(master_path, project_root)
        ffmpeg_run(
            master_path,
            f"crop=1024:{CAPTION_CROP_HEIGHT}:0:{caption_y},scale=1536:765:flags=lanczos",
            text_path, project_root,
        )

    # bw 层
    bw_filter = (
        "crop=1024:1024:0:512,format=gray,eq=contrast=1.18:brightness=0.035,unsharp=5:5:0.55:5:5:0"
        if text_mode_image2
        else "format=gray,eq=contrast=1.18:brightness=0.035,unsharp=5:5:0.55:5:5:0"
    )
    ffmpeg_run(master_path, bw_filter, bw_path, project_root)

    # color 层
    color_filter = "crop=1024:1024:0:512" if text_mode_image2 else "null"
    ffmpeg_run(master_path, color_filter, color_path, project_root)

    rel = lambda p: f"assets/{p.relative_to(project_root / 'public' / 'assets').as_posix()}"
    return {
        "text_image": rel(text_path) if text_mode_image2 else None,
        "bw": rel(bw_path),
        "detail": None,
        "color": rel(color_path),
    }


# ============================================================================
# Prompt 模板（直接照抄 story-to-video.mjs）
# ============================================================================

def build_character_reference_prompt(character_lock: str) -> str:
    return f"""Use case: illustration-story
Asset type: fixed protagonist character reference sheet for a hand-drawn Chinese diary-comic video
Input images: the supplied black-and-white and color frames are style references only. Ignore their people, composition and Chinese text.
Primary request: draw ONLY the recurring protagonists described below. Show each protagonist in two simple full-body poses, front view and three-quarter view, arranged side by side.
Character lock: {character_lock}
Style: {STYLE_LOCK}
Composition: pure white square canvas, all uncropped full-body poses centered with generous spacing and a clean 10% safe border. No scenery, furniture, extra people, props or decorative marks.
Color: selective muted wax-crayon color only. Follow the clothing colors in the character lock, use black scribbles for hair and dark trousers, and leave skin and most of the canvas white.
Constraints: this is an identity reference only; no text, letters, numbers, labels, captions, speech bubbles, logo, signature or watermark; no realistic shading, gradients or vector cleanliness.""".strip()


def build_master_prompt(
    text: str,
    caption: str,
    visual_direction: str,
    character_lock: str,
    text_mode_image2: bool,
) -> str:
    master_size = "1024x1536" if text_mode_image2 else "1024x1024"
    if text_mode_image2:
        caption_panel = (
            f'Top copy panel (pixels y=0–510): pure white background. Write ONLY this '
            f'Simplified Chinese caption verbatim, preserving the explicit line breaks:\n'
            f'"{caption}"\n'
            f'Use thick casual black felt-tip handwriting, 1–3 lines only, generous '
            f'48-pixel left/right margins, and a large readable letter size. Do not put '
            f'any illustration or decorative mark in this panel. Do not place text below y=510.'
        )
        text_constraint = (
            "no extra text outside the exact top caption, no letters or numbers in the "
            "illustration, no labels, captions, speech bubbles, logo, signature or watermark"
        )
        illustration_panel = (
            "Illustration panel (pixels y=512–1536): use this exact lower 1024×1024 square "
            "for the scene. Keep the upper 510-pixel copy panel completely free of any illustration."
        )
    else:
        caption_panel = "Use the entire canvas only for the illustration; do not add any text."
        text_constraint = (
            "no text, letters, numbers, labels, captions, speech bubbles, logo, "
            "signature or watermark"
        )
        illustration_panel = "Use the entire 1024×1024 square for the scene."

    return f"""Use case: illustration-story
Asset type: one vertical production master ({master_size}) for a hand-drawn Chinese diary-comic video. This single output will be locally split into a handwritten caption plate and a color illustration plate.
Input images: the supplied original-video frames are style references; the fixed protagonist character sheet is the identity reference. Ignore all text in references.
Narrative sentence to illustrate: "{text}"
Scene direction: {visual_direction}
Create one concrete, immediately readable tableau for that sentence. Use the locked recurring protagonists whenever the current sentence requires them.
Character lock: {character_lock}
Style: {STYLE_LOCK}
{caption_panel}
{illustration_panel}
Composition: use a comfortably wide camera view. Keep the entire sparse scene in the lower-middle of its illustration square with generous white negative space. Reserve a clean white safe border of at least 10% on the left and right and 8% on the top and bottom. Every figure, limb, prop, building edge, roof, tree branch, rain stroke and motion mark must stay completely inside that safe border. Scale the scene down when necessary; never let any visible mark touch or cross a canvas edge.
Color: selective muted wax-crayon color only: sage green, dusty blue, warm tan, brick red and warm yellow. Keep hair, trousers and other dark areas as black scribbles. Leave skin and most of the canvas pure white.
Continuity: preserve the locked character design. Use the fixed character sheet only for the protagonist's identity, never copy its pose or composition. Include only people required by the current narrative sentence.
Narrative isolation: the character lock defines identities, not an automatic cast list. Show only characters explicitly named in the current sentence or strictly required for its immediate action. Never add family bystanders. Never show a future daughter, rescued child, grandmother, father or any other supporting character before that person is introduced by the narration. Do not carry any person, prop or setting forward merely because it appeared in another scene.
Constraints: non-graphic, emotionally restrained family storytelling; no visible impact, blood, wounds, bruises or injury; no cropped or partially visible subject, prop or background structure; no close-up framing; {text_constraint}; no graphite realism, gradients, detailed scenery or vector cleanliness.""".strip()


# ============================================================================
# 主流程
# ============================================================================

def safe_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title)
    cleaned = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE)
    return cleaned.strip("-")[:32] or "story"


def main():
    parser = argparse.ArgumentParser(
        description="故事文本 → agnes/apiz 生成 master → ffmpeg 切三层 → storyboard.json",
    )
    parser.add_argument("input", help="story.txt 路径（UTF-8）")
    parser.add_argument(
        "--backend", choices=["agnes", "apiz"], default=DEFAULT_BACKEND,
        help=f"图片后端：agnes Agnes Image 2.1 Flash 默认且免费 / apiz fal-ai/nano-banana-2 收费",
    )
    parser.add_argument("--title", default="手绘故事", help="故事标题（用于资产目录命名）")
    parser.add_argument(
        "--character-lock", default=DEFAULT_CHARACTER_LOCK,
        help="角色一致性约束（默认通用版）",
    )
    parser.add_argument(
        "--visual-plan", help="可选 visual_plan.json（场景 id → 视觉方向）",
    )
    parser.add_argument(
        "--text-mode", choices=["image2", "font"], default=None,
        help="caption 渲染方式：image2（图片模型画手写体，仅 apiz 支持） / font（MaShanZheng 字体，agnes 必须用这个）。不传时按后端自动选：agnes→font，apiz→image2",
    )
    parser.add_argument(
        "--transition", choices=["cut", "page-flip"], default="cut",
        help="转场：cut 直接切（默认） / page-flip 右下角卷页",
    )
    parser.add_argument(
        "--transition-sec", type=float, default=0.7,
        help="page-flip 转场秒数（0–2，默认 0.7）",
    )
    parser.add_argument(
        "--model", default=DEFAULT_IMAGE_MODEL,
        help=f"apiz 模型 id（默认 {DEFAULT_IMAGE_MODEL}）",
    )
    parser.add_argument(
        "--no-character-ref", action="store_true",
        help="跳过生成 00_character_reference.png（不推荐，会丢失角色一致性）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印 prompt 和计划，不实际生成图片",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="已存在的 master 也重新生成（默认跳过）",
    )
    args = parser.parse_args()

    # text_mode 未显式指定时按后端自动选：agnes 不会画中文，必须用 font；apiz 默认 image2
    if args.text_mode is None:
        args.text_mode = "font" if args.backend == "agnes" else "image2"
        print(f"  ℹ️ --text-mode 未指定，按后端 {args.backend} 自动选 {args.text_mode}")

    project_root = Path.cwd()
    story_path = Path(args.input).resolve()
    if not story_path.exists():
        raise SystemExit(f"故事文件不存在: {story_path}")

    source_text = story_path.read_text(encoding="utf-8")
    story_parts = split_story(source_text)
    if not story_parts:
        raise SystemExit("故事文本里没找到可用句子")

    print(f"分句完成：{len(story_parts)} 句")
    for i, part in enumerate(story_parts, 1):
        print(f"  {i:02d}. {part}")

    # 计算资产目录 hash（避免不同故事冲突）
    hash_input = "\n".join([
        f"{args.backend}-v1",
        args.title,
        args.text_mode,
        args.transition,
        str(args.transition_sec),
        args.character_lock,
        source_text,
    ])
    story_hash = hashlib.sha256(hash_input.encode("utf-8")).digest().hex()[:8]
    asset_set = f"{safe_title(args.title)}-{story_hash}"
    asset_dir = project_root / "public" / "assets" / "generated" / asset_set
    prompt_dir = project_root / "prompts" / asset_set
    asset_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n资产目录: public/assets/generated/{asset_set}/")

    # 校验参考图存在（apiz generate --image-url 需要它们做风格锚点）
    ref_bw = project_root / "references" / "style-bw.png"
    ref_color = project_root / "references" / "style-color.png"
    if not (ref_bw.exists() and ref_color.exists()):
        raise SystemExit(
            f"缺少风格参考图: {ref_bw} / {ref_color}\n"
            f"模板应自带这两张图（来自 story-to-handdrawn-video-main/references/）"
        )

    visual_plan = {}
    if args.visual_plan:
        visual_plan = json.loads(Path(args.visual_plan).read_text(encoding="utf-8"))

    # —— Step 1: 生成 character_reference（除非 --no-character-ref）——
    char_ref_url = None  # apiz CDN URL（仅 apiz 后端用）
    char_ref_path = asset_dir / "00_character_reference.png"
    if not args.no_character_ref:
        if char_ref_path.exists() and not args.force:
            print(f"\n✓ character_reference 已存在，跳过（--force 可重生成）")
        else:
            char_prompt = build_character_reference_prompt(args.character_lock)
            (prompt_dir / "00_character_reference.txt").write_text(
                char_prompt + "\n", encoding="utf-8"
            )
            if args.dry_run:
                print("\n[dry-run] character_reference prompt:")
                print(char_prompt[:300] + "...")
            else:
                print(f"\n生成 character_reference ({args.backend}) ...")
                if args.backend == "agnes":
                    # agnes 文生图，无上传步骤（后续 master 走图生图时直接传 data URI）
                    agnes_generate_image(
                        prompt=char_prompt,
                        out_path=char_ref_path,
                        model=AGNES_DEFAULT_MODEL,
                        size="2K",
                        ratio="1:1",  # 角色 reference 是正方形
                    )
                else:
                    apiz_generate_image(
                        prompt=char_prompt,
                        out_path=char_ref_path,
                        model=args.model,
                        image_size="square_hd",
                    )
        if char_ref_path.exists() and args.backend == "apiz":
            print("上传 character_reference 到 apiz CDN（给后续 master 当参考）...")
            try:
                char_ref_url = apiz_upload(char_ref_path, folder="story-handdrawn")
                print(f"  ✓ {char_ref_url}")
            except RuntimeError as e:
                print(f"  ⚠️ 上传失败 ({e})，后续 master 将不带 character 参考图（角色一致性可能下降）")
                char_ref_url = None

    # —— Step 2: 每句生成 master + 切三层 ——
    scenes = []
    for i, text in enumerate(story_parts, 1):
        sid = f"{i:02d}"
        caption = format_caption(text)
        duration = duration_for(caption)
        visual_direction = str(
            visual_plan.get(sid)
            or "Stage one simple visual beat that expresses only the current sentence."
        )
        master_path = asset_dir / f"{sid}_master.png"
        prompt = build_master_prompt(
            text=text, caption=caption, visual_direction=visual_direction,
            character_lock=args.character_lock, text_mode_image2=(args.text_mode == "image2"),
        )
        (prompt_dir / f"{sid}_master.txt").write_text(prompt + "\n", encoding="utf-8")

        if master_path.exists() and not args.force:
            print(f"\n[{sid}] master 已存在，跳过生成")
        elif args.dry_run:
            print(f"\n[{sid}] [dry-run] master prompt:")
            print(f"  sentence: {text}")
            print(f"  caption: {caption.replace(chr(10), ' / ')}")
            print(f"  duration: {duration}s")
            print(f"  prompt first 200 chars: {prompt[:200]}...")
        else:
            print(f"\n[{sid}] 生成 master ({args.backend}) ...")
            if args.backend == "agnes":
                # agnes 图生图：character_reference 直接以 data URI 传入 extra_body.image
                agnes_generate_image(
                    prompt=prompt,
                    out_path=master_path,
                    model=AGNES_DEFAULT_MODEL,
                    size="2K",
                    ratio="2:3",  # 与 master 1024×1536 同比例
                    image_ref=char_ref_path if char_ref_path.exists() else None,
                )
            else:
                # apiz 图生图：character_reference 上传到 CDN，--image-url 引用
                image_url_for_gen = char_ref_url
                apiz_generate_image(
                    prompt=prompt,
                    out_path=master_path,
                    model=args.model,
                    image_size="portrait_4_3",  # 1080×1440 比例
                    image_url=image_url_for_gen,
                )

        # 切三层（除非 dry-run）
        if not args.dry_run and master_path.exists():
            assets = split_master_into_layers(
                master_path=master_path, asset_dir=asset_dir, scene_id=sid,
                project_root=project_root, text_mode_image2=(args.text_mode == "image2"),
            )
        else:
            # dry-run 时只填占位路径
            assets = {
                "text_image": f"assets/generated/{asset_set}/{sid}_text.png" if args.text_mode == "image2" else None,
                "bw": f"assets/generated/{asset_set}/{sid}_bw.png",
                "detail": None,
                "color": f"assets/generated/{asset_set}/{sid}_color.png",
            }

        scenes.append({
            "id": sid,
            "duration_sec": duration,
            "text": caption,
            "narration": text,  # TTS 用原文（含上下文，比 caption 长）
            "visual": f"根据文案绘制一个单一、清楚、可画的白底日记漫画场景：{text}",
            "shot": "story_beat",
            "layers": ["text", "bw_full", "color"],
            "color_hint": "仅使用元视频的鼠尾草绿、灰蓝、浅棕、砖红、暖黄等低饱和蜡笔色，保留大量纯白",
            "detail_hint": None,
            "assets": assets,
        })

    # —— Step 3: 写 storyboard.json ——
    storyboard = {
        "project": {
            "title": args.title,
            "mode": "speed",
            "images_per_scene": 1,
            "derive_bw": "local",
            "enable_detail": False,
            "gen_size": 1024,
            "export_size": [1080, 1440],
            "ratio": "3:4",
            "width": 1080,
            "height": 1440,
            "fps": 30,
            "transition": args.transition,
            "transition_sec": args.transition_sec,
            "style_lock": STYLE_LOCK,
            "character_lock": args.character_lock,
            "image_generator": f"{args.backend}-{'agnes-image-2.1-flash' if args.backend == 'agnes' else 'nano-banana-2'}",
            "audio": {
                "voiceover": "pending",  # 跑完 gen_tts + apply_timeline 后变 'active'
                "default_backend": "minimax",
                "bgm": "optional_bed_only",
                "bgm_follows_text": False,
            },
        },
        "scenes": scenes,
    }

    out_path = project_root / "storyboard.json"
    out_path.write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n{'='*60}")
    print(f"✓ storyboard 写入 {out_path}")
    print(f"  场景数: {len(scenes)}")
    print(f"  转场: {args.transition}" + (f" ({args.transition_sec}s)" if args.transition == "page-flip" else ""))
    if args.dry_run:
        print("\n[dry-run] 没有实际生成图片。去掉 --dry-run 跑实际生成。")
    else:
        print("\n下一步：")
        print("  1. python ../../scripts/gen_tts.py narration.yaml --out-dir public/audio/narration")
        print("  2. python ../../scripts/apply_timeline.py")
        print("  3. npm run render:preview  # 720×960 预览")


if __name__ == "__main__":
    main()
