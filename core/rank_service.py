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

from .card_renderer import render_rice_rank_png

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

    async def get_rank_card(
        self,
        umo: str = "",
        profiles: dict[str, dict] | None = None,
    ) -> str:
        rows = await asyncio.to_thread(self._query_group_user_tokens, umo)
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
            )
        )

    def get_my_tokens(self, umo: str, user_id: str) -> dict[str, int]:
        group_id = _group_id_from_umo(umo)
        user_id = str(user_id or "").strip()
        if not group_id or not user_id or len(user_id) > 64:
            return {"tokens": 0, "chats": 0}
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
            row = connection.execute(
                """
                SELECT
                    COALESCE(SUM(token_input_other + token_input_cached + token_output), 0),
                    COUNT(*)
                FROM provider_stats
                WHERE agent_type = 'internal'
                  AND created_at >= ?
                  AND umo = ?
                """,
                (today_start_utc, _user_umo(umo, user_id)),
            ).fetchone()
        except Exception as err:
            logger.warning(f"读取个人大米饭用量失败: {type(err).__name__}")
            return {"tokens": 0, "chats": 0}
        finally:
            if connection is not None:
                connection.close()
        return {"tokens": int(row[0] or 0), "chats": int(row[1] or 0)}

    def _query_group_user_tokens(self, umo: str) -> list[dict]:
        group_id = _group_id_from_umo(umo)
        if not group_id:
            return []
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
                LIMIT ?
                """,
                (today_start_utc, group_id, self.rank_limit),
            ).fetchall()
        except Exception as err:
            logger.warning(f"读取大米饭用量失败: {err}")
            return []
        finally:
            if connection is not None:
                connection.close()
        ranked = []
        for user_id, tokens, chats in rows:
            user_id = str(user_id or "")
            if not user_id or "_" in user_id:
                continue
            ranked.append(
                {
                    "user_id": user_id,
                    "tokens": int(tokens or 0),
                    "chats": int(chats or 0),
                }
            )
        return ranked


def _group_id_from_umo(umo: str) -> str:
    parts = umo.split(":")
    if len(parts) < 3 or parts[1] != "GroupMessage":
        return ""
    session_id = parts[2]
    if "_" in session_id:
        return session_id.rsplit("_", 1)[1]
    return session_id


def _user_umo(umo: str, user_id: str) -> str:
    parts = umo.split(":")
    if len(parts) < 3 or parts[1] != "GroupMessage":
        return ""
    return f"{parts[0]}:GroupMessage:{user_id}_{_group_id_from_umo(umo)}"


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
