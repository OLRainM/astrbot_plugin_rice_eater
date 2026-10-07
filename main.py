import os

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import At
from astrbot.core.platform.astr_message_event import AstrMessageEvent

from .core.rank_service import RankService


class RiceEaterPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.rank_service = RankService(config)

    @filter.command("tokens")
    async def tokens_command(self, event: AstrMessageEvent, action: str = "list"):
        """使用 tokens list 查看群排名，tokens self 查看自己，tokens yours @用户 查看他人"""
        action = str(action).strip().lower()
        if action == "self":
            async for result in self.my_rice(event):
                yield result
            return
        if action == "yours":
            async for result in self.your_rice(event):
                yield result
            return
        if action == "list":
            async for result in self.who_ate_rice(event):
                yield result
            return
        yield event.plain_result(
            "用法：tokens list 查看群排名，tokens self 查看自己，tokens yours @用户 查看他人最近调用。"
        )

    @filter.command("我吃了多少大米饭")
    async def my_rice(self, event: AstrMessageEvent):
        """查看自己本群最近几次模型调用"""
        async for result in self._reply_user_card(event, event.get_sender_id()):
            yield result

    @filter.command("你吃了多少大米饭")
    async def your_rice(self, event: AstrMessageEvent):
        """查看被 @ 用户本群最近几次模型调用"""
        user_id = _mentioned_user_id(event)
        if not user_id:
            yield event.plain_result("请 @ 要查询的用户，例如：你吃了多少大米饭 @某人")
            return
        async for result in self._reply_user_card(event, user_id):
            yield result

    async def _reply_user_card(self, event: AstrMessageEvent, user_id: str):
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令。")
            return
        card_path = await self.rank_service.get_self_card(
            event.unified_msg_origin,
            user_id,
        )
        try:
            yield event.image_result(card_path)
        finally:
            try:
                os.remove(card_path)
            except FileNotFoundError:
                pass
            except OSError as err:
                logger.debug(f"清理个人调用图片失败: {type(err).__name__}")

    @filter.command("谁吃了大米饭")
    async def who_ate_rice(self, event: AstrMessageEvent):
        """查看本群今日谁吃了多少大米饭"""
        if self.rank_service.only_admin and not event.is_admin():
            return
        profiles = await self._group_member_profiles(event)
        card_path = await self.rank_service.get_rank_card(
            event.unified_msg_origin,
            profiles,
        )
        try:
            yield event.image_result(card_path)
        finally:
            try:
                os.remove(card_path)
            except FileNotFoundError:
                pass
            except OSError as err:
                logger.debug(f"清理大米饭排名图片失败: {type(err).__name__}")

    async def _group_member_profiles(self, event: AstrMessageEvent) -> dict[str, dict]:
        group_id = event.get_group_id()
        if not group_id:
            return {}
        bot = getattr(event, "bot", None)
        if bot is None or not hasattr(bot, "call_action"):
            return {}
        group_id_value = int(group_id) if str(group_id).isdigit() else group_id
        routing = {}
        self_id = event.get_self_id()
        if str(self_id).isdigit():
            routing["self_id"] = int(self_id)
        try:
            members = await bot.call_action(
                "get_group_member_list",
                group_id=group_id_value,
                no_cache=True,
                **routing,
            )
        except Exception as err:
            logger.warning(f"获取群成员资料失败: {type(err).__name__}")
            return {}
        profiles: dict[str, dict] = {}
        member_rows = _member_rows(members)
        if not member_rows:
            logger.warning("获取群成员资料失败: 返回结构不是列表")
            return profiles
        remarks = await self._friend_remarks(bot, routing)
        for member in member_rows:
            user_id = str(member.get("user_id") or "").strip()
            if not user_id or len(user_id) > 64:
                continue
            name = (
                remarks.get(user_id)
                or str(member.get("card") or "").strip()
                or str(member.get("nickname") or "").strip()
                or user_id
            )
            avatar_url = _avatar_url(member, user_id)
            profiles[user_id] = {
                "name": name[:128],
                "avatar_url": avatar_url,
            }
        return profiles

    async def _friend_remarks(self, bot, routing: dict) -> dict[str, str]:
        try:
            friends = await bot.call_action("get_friend_list", **routing)
        except Exception as err:
            logger.debug(f"获取好友备注失败: {type(err).__name__}")
            return {}
        remarks: dict[str, str] = {}
        for friend in _member_rows(friends):
            user_id = str(friend.get("user_id") or "").strip()
            remark = str(friend.get("remark") or "").strip()
            if user_id and remark and len(user_id) <= 64:
                remarks[user_id] = remark[:128]
        return remarks


def _member_rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    for source in (data, payload):
        if not isinstance(source, dict):
            continue
        for key in ("member_list", "members", "friend_list", "friends", "list"):
            rows = source.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _mentioned_user_id(event: AstrMessageEvent) -> str:
    for component in event.get_messages():
        if not isinstance(component, At):
            continue
        user_id = str(getattr(component, "qq", "") or "").strip()
        if not user_id or user_id.lower() == "all":
            continue
        if len(user_id) > 64 or any(char in user_id for char in "\\_%"):
            continue
        return user_id
    return ""


def _avatar_url(member: dict, user_id: str) -> str:
    for key in ("avatar", "avatar_url", "headimgurl", "head_img", "user_avatar"):
        value = str(member.get(key) or "").strip()
        if value.startswith(("https://", "http://")):
            return value[:512]
    if user_id.isdigit():
        return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
    return ""
