from __future__ import annotations

import hashlib
import io
import os
import re
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from astrbot.api import logger
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


def render_rice_rank_png(
    rows: list[dict],
    timestamp: str,
    output_path: Path,
    group_tokens: int | None = None,
) -> Path:
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
    today_text = f"TODAY  /  {timestamp}"
    _text(draw, 78, 190, today_text, 16, _MUTED)
    if group_tokens is not None:
        total_text = f"GROUP  {_format_rank_tokens(int(group_tokens))}"
        _text(
            draw,
            _WIDTH - 76 - _text_width(total_text, 16),
            190,
            total_text,
            16,
            _BLACK,
        )

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
    layer = Image.new("RGBA", (width + 240, height), (*_paper_rgb(), 255))
    _draw_mixed_text(layer, 0, 0, " ".join(text.split()), size, fill, chinese)
    if _text_width(" ".join(text.split()), size, chinese) > width:
        fade = Image.new("RGB", (28, height), _PAPER)
        layer.paste(fade, (width - 28, 0))
    image.paste(layer.crop((0, 0, width, height)), (left, top), layer.crop((0, 0, width, height)))


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
        glyph = _inline_glyph(cluster, size, fill)
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
        glyph = _inline_glyph(cluster, size, _BLACK)
        if glyph is not None:
            width += glyph.width + max(1, size // 12)
            continue
        width += int(body.getlength(cluster))
    return width


def _text_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    index = 0
    chars = list(_expand_qq_emoji(text))
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
        raw = "".join(chars[index:end])
        clusters.extend(_emoji_pieces(raw))
        index = end
    return clusters


def _emoji_pieces(text: str) -> list[str]:
    """Draw every emoji base character by itself.

    Pillow on Windows does not shape ZWJ sequences or flags into one color
    glyph. Passing the whole sequence through the body font paints boxes,
    and the color font paints the pieces with stray joiners between them.
    """
    return [
        char
        for char in text
        if _starts_emoji(char) or unicodedata.combining(char)
    ]


def _starts_emoji(char: str) -> bool:
    code = ord(char)
    return _is_emoji_char(char) and code not in {0x200D, 0x20E3, 0xFE0F} and not (
        0xFE00 <= code <= 0xFE0F
    ) and not unicodedata.combining(char)


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


def _inline_glyph(text: str, size: int, fill: str) -> Image.Image | None:
    qq_id = _QQ_EMOJI_IDS.get(text)
    if qq_id is not None:
        return _qq_glyph(qq_id, size)
    if _is_emoji_cluster(text):
        return _emoji_glyph(text, size, fill)
    return None


def _expand_qq_emoji(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        code = ord(match.group(1))
        if code in _QQ_CODE_TO_ID:
            return chr(_QQ_PUA + code)
        return match.group(0)

    return _QQ_TOKEN.sub(replace, text)


def _qq_glyph(emoji_id: str, size: int) -> Image.Image | None:
    cached = _QQ_GLYPHS.get((emoji_id, size))
    if cached is not None or (emoji_id, size) in _QQ_GLYPHS:
        return cached
    path = _qq_emoji_path(emoji_id)
    glyph = None
    if path is not None:
        try:
            image = Image.open(path).convert("RGBA")
            glyph = image.resize((size, size), Image.Resampling.LANCZOS)
        except OSError:
            glyph = None
    _QQ_GLYPHS[(emoji_id, size)] = glyph
    return glyph


def _qq_emoji_path(emoji_id: str) -> Path | None:
    bundled = Path(__file__).resolve().parents[1] / "assets" / "qq" / f"{emoji_id}.png"
    if bundled.exists():
        return bundled
    root = Path(r"C:\Program Files\Tencent")
    if root.exists():
        matches = sorted(root.glob(f"QQNT/versions/*/resources/app/resource/default-emojis/{emoji_id}.png"))
        if matches:
            return matches[-1]
    return None


def _paper_rgb() -> tuple[int, int, int]:
    return tuple(int(_PAPER[index : index + 2], 16) for index in (1, 3, 5))


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
    bitmap_size = _EMOJI_BITMAP if embedded_color else size
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
    paths = (
        (_cached_emoji_font(), True),
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


_EMOJI_BITMAP = 109
_EMOJI_FONT_CANDIDATES: list[tuple[str, bool]] = []
_EMOJI_FONT_SHA256 = "72a635cb3d2f3524c51620cdde406b217204e8a6a06c6a096ff8ed4b5fd6e27b"
_EMOJI_FONT_URL = (
    "https://github.com/OLRainM/astrbot_plugin_rice_eater/releases/download/"
    "emoji-font-v2.051/NotoColorEmoji.ttf"
)
_EMOJI_FONT_CANDIDATES: list[tuple[str, bool]] = []
_EMOJI_FONT_DOWNLOAD_SECONDS = 30


class EmojiFontError(TimeoutError):
    """彩色表情字体下载失败。"""


def prepare_emoji_font() -> None:
    """Use a verified cached font. Never download during card rendering."""
    path = _emoji_font_cache_path()
    if path is not None and _emoji_font_digest_ok(path):
        _reset_emoji_font_candidates()
        return
    logger.info("彩色表情字体未安装，使用系统字体")
    _reset_emoji_font_candidates()


def download_emoji_font() -> str:
    """Download only when explicitly requested. Raise after 30 seconds."""
    path = _emoji_font_cache_path()
    if path is not None and _emoji_font_digest_ok(path):
        _reset_emoji_font_candidates()
        return "彩色表情字体已存在，无需重复下载。"
    try:
        if not _download_emoji_font(path):
            raise EmojiFontError("彩色表情字体下载失败")
    except EmojiFontError:
        _reset_emoji_font_candidates()
        raise
    except Exception as err:
        _reset_emoji_font_candidates()
        raise EmojiFontError("彩色表情字体下载失败") from err
    _reset_emoji_font_candidates()
    return "彩色表情字体下载完成。"


def _emoji_font_cache_path() -> Path | None:
    configured_root = os.environ.get("ASTRBOT_ROOT")
    if configured_root:
        root = Path(configured_root) / "data" / "plugin_data" / "astrbot_plugin_rice_eater"
    elif os.name == "nt" and (
        "ASTRBOT_DESKTOP" in os.environ
        or (Path.home() / ".astrbot" / "data" / "data_v4.db").exists()
    ):
        root = Path.home() / ".astrbot" / "data" / "plugin_data" / "astrbot_plugin_rice_eater"
    else:
        root = Path.cwd() / "data" / "plugin_data" / "astrbot_plugin_rice_eater"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return root / "NotoColorEmoji.ttf"


def _cached_emoji_font() -> Path:
    path = _emoji_font_cache_path()
    if path is not None and _emoji_font_digest_ok(path):
        return path
    return Path("__missing_emoji_font__")


def _emoji_font_digest_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return False
    return digest.hexdigest() == _EMOJI_FONT_SHA256


def _download_emoji_font(path: Path | None) -> bool:
    if path is None:
        return False
    temporary = path.with_suffix(".ttf.part")
    try:
        with urllib.request.urlopen(
            _EMOJI_FONT_URL,
            timeout=_EMOJI_FONT_DOWNLOAD_SECONDS,
        ) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                return False
            with temporary.open("wb") as handle:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 20 * 1024 * 1024:
                        raise ValueError("emoji font exceeds size limit")
                    handle.write(chunk)
        if not _emoji_font_digest_ok(temporary):
            logger.warning("彩色表情字体 SHA256 校验失败，回退到系统字体")
            return False
        temporary.replace(path)
        return True
    except TimeoutError as err:
        raise EmojiFontError("彩色表情字体下载超时") from err
    except urllib.error.URLError as err:
        if isinstance(getattr(err, "reason", None), TimeoutError):
            raise EmojiFontError("彩色表情字体下载超时") from err
        logger.info(f"彩色表情字体下载失败，回退到系统字体: {type(err).__name__}")
        return False
    except (OSError, ValueError) as err:
        logger.info(f"彩色表情字体下载失败，回退到系统字体: {type(err).__name__}")
        return False
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _reset_emoji_font_candidates() -> None:
    _EMOJI_FONT_CANDIDATES.clear()
    _EMOJI_GLYPHS.clear()
_EMOJI_GLYPHS: dict[tuple[str, int, str], Image.Image | None] = {}
_QQ_PUA = 0xE000
_QQ_TOKEN = re.compile(r"<\$([^<>])>")
_QQ_CODE_TO_ID = {
    0x00B2: "178",  # <$²> 斜眼笑
    0x0092: "146",  # <$> 爆筋
    0x0005: "5",  # 流泪
    0x0137: "311",  # 打call
    0x0138: "312",  # 变形
    0x0139: "314",  # 仔细分析
    0x013A: "317",  # 菜汪
    0x013D: "318",  # 崇拜
    0x013E: "319",  # 比心
    0x013F: "320",  # 庆祝
    0x0140: "324",  # 吃糖
    0x0141: "325",  # 惊吓
    0x0151: "337",  # 花朵脸
    0x0152: "338",  # 我想开了
    0x0153: "339",  # 舔屏
    0x0154: "341",  # 打招呼
    0x0072: "114",  # 篮球
    0x0146: "326",  # 生气
    0x0035: "53",  # 蛋糕
    0x0089: "137",  # 鞭炮
    0x014D: "333",  # 烟花
    0x0000: "14",
    0x0001: "1",
    0x0002: "2",
    0x0003: "3",
    0x0004: "4",
    0x0006: "6",
    0x0007: "7",
    0x0008: "8",
    0x0009: "9",
    0x000A: "10",
    0x000B: "11",
    0x000C: "12",
    0x000D: "13",
    0x000E: "0",
    0x000F: "15",
    0x0010: "16",
    0x0011: "96",
    0x0012: "18",
    0x0013: "19",
    0x0014: "20",
    0x0015: "21",
    0x0016: "22",
    0x0017: "23",
    0x0018: "24",
    0x0019: "25",
    0x001A: "26",
    0x001B: "27",
    0x001C: "28",
    0x001D: "29",
    0x001E: "30",
    0x001F: "31",
    0x007F: "32",
    0x0080: "33",
    0x0081: "34",
    0x0082: "35",
    0x0083: "36",
    0x0084: "37",
    0x0085: "38",
    0x0086: "39",
    0x0087: "97",
    0x0088: "98",
    0x008A: "99",
    0x008B: "100",
    0x008C: "101",
    0x008D: "102",
    0x008E: "103",
    0x008F: "104",
    0x0090: "105",
    0x0091: "106",
    0x0093: "107",
    0x0094: "108",
    0x0095: "305",
    0x0096: "109",
    0x0097: "110",
    0x0098: "111",
    0x0099: "172",
    0x009A: "182",
    0x009B: "179",
    0x009C: "173",
    0x009D: "174",
    0x009E: "212",
    0x009F: "175",
    0x00A1: "177",
    0x00A2: "176",
    0x00A3: "183",
    0x00A4: "262",
    0x00A5: "263",
    0x00A6: "264",
    0x00A7: "265",
    0x00A8: "266",
    0x00A9: "267",
    0x00AA: "268",
    0x00AB: "269",
    0x00AC: "270",
    0x00AD: "271",
    0x00AE: "272",
    0x00AF: "277",
    0x00B0: "307",
    0x00B1: "306",
    0x00B3: "281",
    0x00B4: "282",
    0x00B5: "283",
    0x00B6: "284",
    0x00B7: "285",
    0x00B8: "293",
    0x00B9: "286",
    0x00BA: "287",
    0x00BB: "289",
    0x00BC: "294",
    0x00BD: "297",
    0x00BE: "298",
    0x00BF: "299",
    0x00C0: "300",
    0x00C1: "323",
    0x00C2: "332",
    0x00C3: "336",
    0x00C4: "353",
    0x00C5: "355",
    0x00C6: "356",
    0x00C7: "354",
    0x00C8: "352",
    0x00C9: "357",
    0x00CA: "428",
    0x00CB: "334",
    0x00CC: "347",
    0x00CD: "303",
    0x00CE: "302",
    0x00CF: "295",
    0x00D0: "49",
    0x00D1: "66",
    0x00D2: "63",
    0x00D3: "64",
    0x00D4: "187",
    0x00D5: "116",
    0x00D6: "67",
    0x00D7: "60",
    0x00D8: "185",
    0x00D9: "76",
    0x00DA: "124",
    0x00DB: "118",
    0x00DC: "78",
    0x00DD: "119",
    0x00DE: "79",
    0x00DF: "120",
    0x00E0: "121",
    0x00E1: "77",
    0x00E2: "123",
    0x00E3: "201",
    0x00E4: "273",
    0x00E5: "46",
    0x00E6: "112",
    0x00E7: "56",
    0x00E8: "169",
    0x00E9: "171",
    0x00EA: "59",
    0x00EB: "144",
    0x00EC: "147",
    0x00ED: "89",
    0x00EE: "41",
    0x00EF: "125",
    0x00F0: "42",
    0x00F1: "43",
    0x00F2: "86",
    0x00F3: "129",
    0x00F4: "85",
}
_QQ_EMOJI_IDS = {chr(_QQ_PUA + code): emoji_id for code, emoji_id in _QQ_CODE_TO_ID.items()}
_QQ_GLYPHS: dict[tuple[str, int], Image.Image | None] = {}


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
