from __future__ import annotations

import asyncio
import datetime
import os
import sqlite3
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_temp_path

from .card_renderer import (
    EmojiFontError,
    download_emoji_font,
    prepare_emoji_font,
    render_rice_rank_png,
    render_self_calls_png,
)

_MAX_AVATAR_BYTES = 2 * 1024 * 1024
_MAX_AVATAR_ITEMS = 20


class RankService:
    def __init__(self, config):
        self.only_admin = config.get("only_admin", False) is True
        try:
            limit = int(config.get("rank_limit", 10) or 10)
        except (TypeError, ValueError):
            limit = 10
        self.rank_limit = min(10, max(1, limit))
        try:
            recent_limit = int(config.get("self_recent_limit", 8) or 8)
        except (TypeError, ValueError):
            recent_limit = 8
        self.self_recent_limit = min(12, max(1, recent_limit))

    async def download_emoji_font(self) -> str:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(download_emoji_font),
                timeout=30,
            )
        except TimeoutError as err:
            raise EmojiFontError("彩色表情字体下载失败") from err

    async def get_rank_card(
        self,
        umo: str = "",
        profiles: dict[str, dict] | None = None,
    ) -> str:
        await asyncio.to_thread(prepare_emoji_font)
        rows, group_tokens = await asyncio.to_thread(self._query_group_user_tokens, umo)
        enriched = [
            {
                **row,
                "name": (profiles or {}).get(row["user_id"], {}).get("name")
                or row["user_id"],
                "avatar_url": (profiles or {}).get(row["user_id"], {}).get("avatar_url")
                or "",
            }
            for row in rows
        ]
        avatars = await _download_avatars(
            [(row["user_id"], row["avatar_url"]) for row in enriched]
        )
        for row in enriched:
            row["avatar"] = avatars.get(row["user_id"])
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        output_path = (
            Path(get_astrbot_temp_path())
            / f"astrbot_plugin_rice_eater_{uuid.uuid4().hex}.png"
        )
        return str(
            await asyncio.to_thread(
                render_rice_rank_png,
                enriched,
                timestamp,
                output_path,
                group_tokens,
            )
        )

    async def get_self_card(self, umo: str, user_id: str) -> str:
        await asyncio.to_thread(prepare_emoji_font)
        calls = await asyncio.to_thread(self._query_recent_calls, umo, user_id)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        output_path = (
            Path(get_astrbot_temp_path())
            / f"astrbot_plugin_rice_eater_self_{uuid.uuid4().hex}.png"
        )
        return str(
            await asyncio.to_thread(
                render_self_calls_png,
                calls,
                _mask_user_id(user_id),
                timestamp,
                output_path,
            )
        )

    def _query_recent_calls(self, umo: str, user_id: str) -> list[dict]:
        user_umo = _user_umo(umo, user_id)
        if not user_umo:
            return []
        db_path = _astrbot_data_dir() / "data_v4.db"
        connection = None
        try:
            connection = sqlite3.connect(
                f"file:{db_path.as_posix()}?mode=ro", uri=True
            )
            rows = connection.execute(
                """
                SELECT
                    created_at,
                    token_input_other,
                    token_input_cached,
                    token_output
                FROM provider_stats
                WHERE agent_type = 'internal'
                  AND umo = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_umo, self.self_recent_limit),
            ).fetchall()
        except Exception as err:
            logger.warning(f"读取最近调用失败: {type(err).__name__}")
            return []
        finally:
            if connection is not None:
                connection.close()
        calls = []
        for created_at, token_input_other, token_input_cached, token_output in rows:
            calls.append(
                {
                    "time": _mask_call_time(created_at),
                    "input_tokens": int(token_input_other or 0)
                    + int(token_input_cached or 0),
                    "output_tokens": int(token_output or 0),
                }
            )
        return calls

    def _query_group_user_tokens(self, umo: str) -> tuple[list[dict], int]:
        group_id = _group_id_from_umo(umo)
        if not group_id:
            return [], 0
        local_now = datetime.datetime.now().astimezone()
        today_start_utc = (
            local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(ZoneInfo("UTC"))
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        db_path = _astrbot_data_dir() / "data_v4.db"
        connection = None
        try:
            connection = sqlite3.connect(
                f"file:{db_path.as_posix()}?mode=ro", uri=True
            )
            rows = connection.execute(
                """
                SELECT
                    substr(
                        substr(umo, instr(umo, ':GroupMessage:') + 14),
                        1,
                        instr(substr(umo, instr(umo, ':GroupMessage:') + 14), '_') - 1
                    ) AS user_id,
                    COALESCE(
                        SUM(token_input_other + token_input_cached + token_output),
                        0
                    ) AS tokens,
                    COUNT(*) AS chats
                FROM provider_stats
                WHERE agent_type = 'internal'
                  AND created_at >= ?
                  AND substr(umo, instr(umo, ':GroupMessage:') + 14)
                      LIKE '%\\_' || ? ESCAPE '\\'
                GROUP BY user_id
                ORDER BY tokens DESC
                """,
                (today_start_utc, group_id),
            ).fetchall()
        except Exception as err:
            logger.warning(f"读取大米饭用量失败: {err}")
            return [], 0
        finally:
            if connection is not None:
                connection.close()
        ranked = []
        group_tokens = 0
        for user_id, tokens, chats in rows:
            user_id = str(user_id or "")
            if not user_id or "_" in user_id:
                continue
            amount = int(tokens or 0)
            group_tokens += amount
            ranked.append(
                {
                    "user_id": user_id,
                    "tokens": amount,
                    "chats": int(chats or 0),
                }
            )
        return ranked[: self.rank_limit], group_tokens


def _group_id_from_umo(umo: str) -> str:
    parts = umo.split(":")
    if len(parts) < 3 or parts[1] != "GroupMessage":
        return ""
    session_id = parts[2]
    if "_" in session_id:
        return session_id.rsplit("_", 1)[1]
    return session_id


def _user_umo(umo: str, user_id: str) -> str:
    user_id = str(user_id or "").strip()
    if not user_id or len(user_id) > 64 or any(char in user_id for char in "\\_%"):
        return ""
    parts = umo.split(":")
    if len(parts) < 3 or parts[1] != "GroupMessage":
        return ""
    group_id = _group_id_from_umo(umo)
    if not group_id:
        return ""
    return f"{parts[0]}:GroupMessage:{user_id}_{group_id}"


def _mask_user_id(user_id: str) -> str:
    value = "".join(char for char in str(user_id or "") if char.isalnum())
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}****{value[-2:]}"


def _mask_call_time(created_at) -> str:
    text = str(created_at or "").strip()
    parsed = None
    for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.datetime.strptime(text[:26], pattern)
            break
        except ValueError:
            continue
    if parsed is None:
        return "--.-- --:**"
    local_time = parsed.replace(tzinfo=ZoneInfo("UTC")).astimezone()
    return f"{local_time.strftime('%m.%d')} {local_time.strftime('%H')}:**"


def _astrbot_data_dir() -> Path:
    configured_root = os.environ.get("ASTRBOT_ROOT")
    if configured_root:
        return Path(configured_root) / "data"
    if os.name == "nt" and "ASTRBOT_DESKTOP" in os.environ:
        return Path.home() / ".astrbot" / "data"
    desktop_data = Path.home() / ".astrbot" / "data" / "data_v4.db"
    if desktop_data.exists():
        return desktop_data.parent
    return Path.cwd() / "data"


async def _download_avatars(items: list[tuple[str, str]]) -> dict[str, bytes]:
    import httpx

    result: dict[str, bytes] = {}
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as client:
        for user_id, url in items[:_MAX_AVATAR_ITEMS]:
            if not url or not url.startswith(("https://", "http://")):
                continue
            try:
                async with client.stream(
                    "GET",
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://qun.qq.com/",
                    },
                ) as response:
                    content_type = response.headers.get("content-type", "").lower()
                    content_length = response.headers.get("content-length")
                    if response.status_code != 200 or "image" not in content_type:
                        continue
                    if content_length and int(content_length) > _MAX_AVATAR_BYTES:
                        logger.warning("头像响应超过大小限制")
                        continue
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > _MAX_AVATAR_BYTES:
                            chunks = []
                            break
                        chunks.append(chunk)
                    if chunks:
                        result[user_id] = b"".join(chunks)
            except (httpx.HTTPError, ValueError) as err:
                logger.debug(f"下载头像失败: {type(err).__name__}")
    return result
