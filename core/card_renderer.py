from __future__ import annotations

import io
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_RED = "#FF3000"
_BLACK = "#111111"
_PAPER = "#F4F1EA"
_MUTED = "#8A8478"
_TRACK = "#E4DFD4"
_WIDTH = 920
_MAX_AVATAR_PIXELS = 12_000_000
Image.MAX_IMAGE_PIXELS = _MAX_AVATAR_PIXELS


def render_self_calls_png(
    calls: list[dict],
    masked_user: str,
    timestamp: str,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    visible = calls[:12]
    height = 318 + max(1, len(visible)) * 72 + 86
    image = Image.new("RGB", (_WIDTH, height), _PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, _WIDTH - 36, height - 36), outline=_BLACK, width=3)
    draw.rectangle((36, 36, 54, height - 36), fill=_RED)
    _text(draw, 78, 54, "最近调用", 22, _RED, chinese=True)
    _text(draw, 78, 88, "SELF", 52, _BLACK)
    title_width = _text_width("SELF", 52)
    _text(draw, 78 + title_width + 16, 88, "CALLS", 52, _RED)
    _text(draw, 78, 158, f"ID  {masked_user}", 18, _BLACK)
    _text(draw, 78, 186, f"LOCAL  /  {timestamp}", 16, _MUTED)
    draw.line((78, 222, _WIDTH - 76, 222), fill=_BLACK, width=2)
    _text(draw, 78, 236, "NO", 14, _MUTED)
    _text(draw, 150, 236, "TIME", 14, _MUTED)
    input_header_x = 470 + _text_width("000,000", 22) - _text_width("INPUT", 14)
    output_header_x = _WIDTH - 76 - _text_width("OUTPUT", 14)
    _text(draw, input_header_x, 236, "INPUT", 14, _MUTED)
    _text(draw, output_header_x, 236, "OUTPUT", 14, _MUTED)

    if not visible:
        _text(draw, 78, 292, "还没有调用记录", 28, _BLACK, chinese=True)
    top = max((int(row.get("input_tokens") or 0) for row in visible), default=1)
    for index, row in enumerate(visible, start=1):
        _draw_call_row(draw, 268 + (index - 1) * 72, index, row, top)

    footer_y = height - 78
    draw.line((78, footer_y, _WIDTH - 76, footer_y), fill=_BLACK, width=1)
    _text(draw, 78, footer_y + 16, f"GRID {len(visible):02d} / MINUTE MASKED", 16, _BLACK)
    draw.rectangle((_WIDTH - 160, footer_y + 16, _WIDTH - 76, footer_y + 34), fill=_RED)
    image.save(output_path, format="PNG")
    return output_path


def _draw_call_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    index: int,
    row: dict,
    top_input: int,
) -> None:
    _text(draw, 78, y + 8, f"{index:02d}", 22, _RED)
    _text(draw, 150, y + 10, str(row.get("time") or "--.-- --:**"), 22, _BLACK)
    input_tokens = int(row.get("input_tokens") or 0)
    output_tokens = int(row.get("output_tokens") or 0)
    input_text = f"{input_tokens:,}"
    output_text = f"{output_tokens:,}"
    input_x = 470 + _text_width("000,000", 22) - _text_width(input_text, 22)
    output_x = _WIDTH - 76 - _text_width(output_text, 22)
    _text(draw, input_x, y + 8, input_text, 22, _BLACK)
    _text(draw, output_x, y + 8, output_text, 22, _BLACK)
    bar_max = 250
    ratio = 0 if top_input <= 0 else input_tokens / top_input
    bar_width = max(8, round(bar_max * ratio)) if input_tokens else 0
    draw.rectangle((150, y + 42, 150 + bar_max, y + 50), fill=_TRACK)
    if bar_width:
        draw.rectangle((150, y + 42, 150 + bar_width, y + 50), fill=_RED)


def render_rice_rank_png(rows: list[dict], timestamp: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    visible = rows[:10]
    height = 236 + max(1, len(visible)) * 84 + 78
    image = Image.new("RGB", (_WIDTH, height), _PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, _WIDTH - 36, height - 36), outline=_BLACK, width=3)
    draw.rectangle((36, 36, 54, height - 36), fill=_RED)
    _text(draw, 78, 58, "谁吃了大米饭", 22, _RED, chinese=True)
    _text(draw, 78, 96, "RICE", 56, _BLACK)
    title_width = _text_width("RICE", 56)
    _text(draw, 78 + title_width + 18, 96, "RANK", 56, _RED)
    draw.line((78, 176, _WIDTH - 76, 176), fill=_BLACK, width=2)
    _text(draw, 78, 190, f"TODAY  /  {timestamp}", 16, _MUTED)

    if not visible:
        _text(draw, 78, 250, "今日还没人吃饭", 28, _BLACK, chinese=True)
    top = visible[0]["tokens"] if visible else 1
    for index, row in enumerate(visible, start=1):
        y = 214 + (index - 1) * 84
        _draw_rank_row(image, draw, y, index, row, top)

    footer_y = height - 78
    draw.line((78, footer_y, _WIDTH - 76, footer_y), fill=_BLACK, width=1)
    _text(draw, 78, footer_y + 16, f"GRID {len(visible):02d} / GROUP SAMPLE", 16, _BLACK)
    draw.rectangle((_WIDTH - 160, footer_y + 16, _WIDTH - 76, footer_y + 34), fill=_RED)
    image.save(output_path, format="PNG")
    return output_path


def _draw_rank_row(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    y: int,
    index: int,
    row: dict,
    top_tokens: int,
) -> None:
    _text(draw, 78, y + 16, f"{index:02d}", 22, _RED)
    avatar = _avatar_image(row.get("avatar"))
    image.paste(avatar, (132, y))
    draw.rectangle((132, y, 188, y + 56), outline=_BLACK, width=1)
    token_text = _format_rank_tokens(int(row.get("tokens") or 0))
    token_width = _text_width(token_text, 24)
    _text(draw, _WIDTH - 76 - token_width, y, token_text, 24, _BLACK)
    chat_text = f"{int(row.get('chats') or 0)} 次"
    chat_width = _text_width(chat_text, 16, chinese=True)
    _fit_text(
        image,
        206,
        y,
        _WIDTH - 76 - token_width - 18,
        y + 30,
        str(row.get("name") or row["user_id"]),
        20,
        _BLACK,
    )
    _text(
        draw,
        _WIDTH - 76 - chat_width,
        y + 34,
        chat_text,
        16,
        _MUTED,
        chinese=True,
    )
    bar_max = _WIDTH - 76 - chat_width - 24 - 206
    ratio = 0 if top_tokens <= 0 else int(row.get("tokens") or 0) / top_tokens
    bar_width = max(8, round(bar_max * ratio)) if int(row.get("tokens") or 0) else 0
    draw.rectangle((206, y + 40, 206 + bar_max, y + 48), fill=_TRACK)
    if bar_width:
        draw.rectangle(
            (206, y + 40, 206 + bar_width, y + 48),
            fill=_RED,
        )


def _avatar_image(raw: bytes | None) -> Image.Image:
    size = 56
    if raw:
        try:
            avatar = Image.open(io.BytesIO(raw)).convert("RGB")
            return avatar.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            pass
    placeholder = Image.new("RGB", (size, size), _TRACK)
    mark = ImageDraw.Draw(placeholder)
    mark.rectangle((0, 0, size - 1, size - 1), outline=_BLACK, width=1)
    mark.rectangle((18, 18, 38, 38), fill=_RED)
    return placeholder


def _format_rank_tokens(value: int) -> str:
    return f"{value:,}"


def _text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    size: int,
    fill: str,
    chinese: bool = False,
) -> None:
    image = getattr(draw, "_image", None) or getattr(draw, "im", None)
    if isinstance(image, Image.Image):
        _draw_mixed_text(image, x, y, text, size, fill, chinese)
        return
    draw.text((x, y), text, font=_font(size, chinese), fill=fill)


def _fit_text(
    image: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
    text: str,
    size: int,
    fill: str,
    chinese: bool = True,
) -> None:
    width = max(1, right - left)
    height = max(1, bottom - top)
    layer = Image.new("RGB", (width + 240, height), _PAPER)
    _draw_mixed_text(layer, 0, 0, " ".join(text.split()), size, fill, chinese)
    if _text_width(" ".join(text.split()), size, chinese) > width:
        fade = Image.new("RGB", (28, height), _PAPER)
        layer.paste(fade, (width - 28, 0))
    image.paste(layer.crop((0, 0, width, height)), (left, top))


def _draw_mixed_text(
    image: Image.Image,
    x: int,
    y: int,
    text: str,
    size: int,
    fill: str,
    chinese: bool,
) -> None:
    draw = ImageDraw.Draw(image)
    cursor = x
    body = _font(size, chinese)
    for cluster in _text_clusters(text):
        if _is_emoji_cluster(cluster):
            glyph = _emoji_glyph(cluster, size, fill)
            if glyph is not None:
                top = y + max(0, (size - glyph.height) // 2)
                image.paste(glyph, (cursor, top), glyph)
                cursor += glyph.width + max(1, size // 12)
                continue
        draw.text((cursor, y), cluster, font=body, fill=fill)
        cursor += int(body.getlength(cluster))


def _text_width(text: str, size: int, chinese: bool = False) -> int:
    body = _font(size, chinese)
    width = 0
    for cluster in _text_clusters(text):
        if _is_emoji_cluster(cluster):
            glyph = _emoji_glyph(cluster, size, _BLACK)
            if glyph is not None:
                width += glyph.width + max(1, size // 12)
                continue
        width += int(body.getlength(cluster))
    return width


def _text_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    index = 0
    chars = list(text)
    while index < len(chars):
        char = chars[index]
        if not _is_emoji_char(char):
            clusters.append(char)
            index += 1
            continue
        end = index + 1
        while end < len(chars) and (
            _is_emoji_char(chars[end]) or unicodedata.combining(chars[end])
        ):
            joiner = chars[end] == "\u200d"
            end += 1
            if joiner and end < len(chars):
                end += 1
        clusters.append("".join(chars[index:end]))
        index = end
    return clusters


def _is_emoji_cluster(text: str) -> bool:
    return any(_is_emoji_char(char) for char in text)


def _is_emoji_char(char: str) -> bool:
    code = ord(char)
    return (
        0x1F000 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x27BF
        or 0xFE00 <= code <= 0xFE0F
        or code in {0x200D, 0x20E3}
        or 0x1F1E6 <= code <= 0x1F1FF
        or 0xE0020 <= code <= 0xE007F
    )


def _emoji_glyph(text: str, size: int, fill: str) -> Image.Image | None:
    cached = _EMOJI_GLYPHS.get((text, size, fill))
    if cached is not None or (text, size, fill) in _EMOJI_GLYPHS:
        return cached
    glyph = _render_emoji_glyph(text, size, fill)
    _EMOJI_GLYPHS[(text, size, fill)] = glyph
    return glyph


def _render_emoji_glyph(text: str, size: int, fill: str) -> Image.Image | None:
    candidates = _emoji_font_candidates()
    color_font = next((item for item in candidates if item[1]), None)
    if color_font is not None:
        glyph = _draw_font_glyph(text, size, color_font[0], embedded_color=True)
        if glyph is not None:
            return glyph
    mono_font = next((item for item in candidates if not item[1]), None)
    if mono_font is None:
        return None
    return _draw_font_glyph(text, size, mono_font[0], embedded_color=False, fill=fill)


def _draw_font_glyph(
    text: str,
    size: int,
    path: str,
    embedded_color: bool,
    fill: str = _BLACK,
) -> Image.Image | None:
    bitmap_size = 109 if embedded_color else size
    try:
        font = ImageFont.truetype(path, bitmap_size)
    except OSError:
        return None
    canvas = max(bitmap_size * 4, 128)
    layer = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (8, 8),
        text,
        font=font,
        fill=fill,
        embedded_color=embedded_color,
    )
    bbox = layer.getbbox()
    if not bbox:
        return None
    glyph = layer.crop(bbox)
    if glyph.height != size:
        glyph = glyph.resize(
            (max(1, round(glyph.width * size / glyph.height)), size),
            Image.Resampling.LANCZOS,
        )
    return glyph


def _emoji_font_candidates() -> list[tuple[str, bool]]:
    if _EMOJI_FONT_CANDIDATES:
        return _EMOJI_FONT_CANDIDATES
    bundled = Path(__file__).resolve().parents[1] / "assets" / "NotoColorEmoji.ttf"
    paths = (
        (bundled, True),
        (Path(r"C:\Windows\Fonts\seguiemj.ttf"), True),
        (Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"), True),
        (Path("/usr/share/fonts/noto/NotoColorEmoji.ttf"), True),
        (Path("/usr/share/fonts/google-noto-emoji/NotoColorEmoji.ttf"), True),
        (Path("/System/Library/Fonts/Apple Color Emoji.ttc"), True),
        (Path(r"C:\Windows\Fonts\seguisym.ttf"), False),
        (Path("/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf"), False),
    )
    for path, color in paths:
        if path.exists():
            _EMOJI_FONT_CANDIDATES.append((str(path), color))
    return _EMOJI_FONT_CANDIDATES


_EMOJI_FONT_CANDIDATES: list[tuple[str, bool]] = []
_EMOJI_GLYPHS: dict[tuple[str, int, str], Image.Image | None] = {}


def _font(size: int, chinese: bool = False) -> ImageFont.ImageFont:
    candidates = (
        (
            (r"C:\Windows\Fonts\msyhbd.ttc", 0),
            (r"C:\Windows\Fonts\msyh.ttc", 0),
            (r"C:\Windows\Fonts\simhei.ttf", 0),
        )
        if chinese
        else (
            (r"C:\Windows\Fonts\arialbd.ttf", 0),
            (r"C:\Windows\Fonts\arial.ttf", 0),
            (r"C:\Windows\Fonts\segoeuib.ttf", 0),
        )
    )
    for candidate, index in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size, index=index)
    return ImageFont.load_default()
