"""Telegram bot classes and utilities."""

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Sequence
import io
import logging
from ssl import SSLContext
from types import MappingProxyType
from typing import Any

import httpx
from telegram import (
    Bot,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputPollOption,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import CallbackContext, filters
from telegram.request import HTTPXRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    CONF_API_KEY,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_BEARER_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

from .const import (
    ATTR_ARGS,
    ATTR_AUTHENTICATION,
    ATTR_CAPTION,
    ATTR_CHAT_ID,
    ATTR_CHAT_INSTANCE,
    ATTR_DATA,
    ATTR_DATE,
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_FILE,
    ATTR_FROM_FIRST,
    ATTR_FROM_LAST,
    ATTR_KEYBOARD,
    ATTR_KEYBOARD_INLINE,
    ATTR_MESSAGE,
    ATTR_MESSAGE_TAG,
    ATTR_MESSAGE_THREAD_ID,
    ATTR_MESSAGEID,
    ATTR_MSG,
    ATTR_MSGID,
    ATTR_ONE_TIME_KEYBOARD,
    ATTR_OPEN_PERIOD,
    ATTR_PARSER,
    ATTR_PASSWORD,
    ATTR_REPLY_TO_MSGID,
    ATTR_REPLYMARKUP,
    ATTR_RESIZE_KEYBOARD,
    ATTR_STICKER_ID,
    ATTR_TEXT,
    ATTR_TIMEOUT,
    ATTR_TITLE,
    ATTR_URL,
    ATTR_USER_ID,
    ATTR_USERNAME,
    ATTR_VERIFY_SSL,
    CONF_CHAT_ID,
    CONF_PROXY_URL,
    DOMAIN,
    EVENT_TELEGRAM_CALLBACK,
    EVENT_TELEGRAM_COMMAND,
    EVENT_TELEGRAM_SENT,
    EVENT_TELEGRAM_TEXT,
    PARSER_HTML,
    PARSER_MD,
    PARSER_MD2,
    PARSER_PLAIN_TEXT,
    SERVICE_EDIT_CAPTION,
    SERVICE_EDIT_MESSAGE,
    SERVICE_SEND_ANIMATION,
    SERVICE_SEND_DOCUMENT,
    SERVICE_SEND_PHOTO,
    SERVICE_SEND_STICKER,
    SERVICE_SEND_VIDEO,
    SERVICE_SEND_VOICE,
)

_LOGGER = logging.getLogger(__name__)

type TelegramBotConfigEntry = ConfigEntry[TelegramNotificationService]


def _get_bot_info(bot: Bot, config_entry: ConfigEntry) -> dict[str, Any]:
    return {
        "config_entry_id": config_entry.entry_id,
        "id": bot.id,
        "first_name": bot.first_name,
        "last_name": bot.last_name,
        "username": bot.username,
    }


class BaseTelegramBot:
    """The base class for the telegram bot."""

    def __init__(
        self, hass: HomeAssistant, config: TelegramBotConfigEntry, bot: Bot
    ) -> None:
        """Initialize the bot base class."""
        self.hass = hass
        self.config = config
        self._bot = bot

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the bot application."""

    async def handle_update(self, update: Update, context: CallbackContext) -> bool:
        """Handle updates from bot application set up by the respective platform."""
        _LOGGER.debug("Handling update %s", update)
        if not self.authorize_update(update):
            return False

        # establish event type: text, command or callback_query
        if update.callback_query:
            # NOTE: Check for callback query first since effective message will be populated with the message
            # in .callback_query (python-telegram-bot docs are wrong)
            event_type, event_data = self._get_callback_query_event_data(
                update.callback_query
            )
        elif update.effective_message:
            event_type, event_data = self._get_message_event_data(
                update.effective_message
            )
        else:
            _LOGGER.warning("Unhandled update: %s", update)
            return True

        event_data["bot"] = _get_bot_info(self._bot, self.config)

        event_context = Context()

        _LOGGER.debug("Firing event %s: %s", event_type, event_data)
        self.hass.bus.async_fire(event_type, event_data, context=event_context)
        return True

    @staticmethod
    def _get_command_event_data(command_text: str | None) -> dict[str, str | list]:
        if not command_text or not command_text.startswith("/"):
            return {}
        command_parts = command_text.split()
        command = command_parts[0]
        args = command_parts[1:]
        return {ATTR_COMMAND: command, ATTR_ARGS: args}

    def _get_message_event_data(self, message: Message) -> tuple[str, dict[str, Any]]:
        event_data: dict[str, Any] = {
            ATTR_MSGID: message.message_id,
            ATTR_CHAT_ID: message.chat.id,
            ATTR_DATE: message.date,
            ATTR_MESSAGE_THREAD_ID: message.message_thread_id,
        }
        if filters.COMMAND.filter(message):
            # This is a command message - set event type to command and split data into command and args
            event_type = EVENT_TELEGRAM_COMMAND
            event_data.update(self._get_command_event_data(message.text))
        else:
            event_type = EVENT_TELEGRAM_TEXT
            event_data[ATTR_TEXT] = message.text

        if message.from_user:
            event_data.update(self._get_user_event_data(message.from_user))

        return event_type, event_data

    def _get_user_event_data(self, user: User) -> dict[str, Any]:
        return {
            ATTR_USER_ID: user.id,
            ATTR_FROM_FIRST: user.first_name,
            ATTR_FROM_LAST: user.last_name,
        }

    def _get_callback_query_event_data(
        self, callback_query: CallbackQuery
    ) -> tuple[str, dict[str, Any]]:
        event_type = EVENT_TELEGRAM_CALLBACK
        event_data: dict[str, Any] = {
            ATTR_MSGID: callback_query.id,
            ATTR_CHAT_INSTANCE: callback_query.chat_instance,
            ATTR_DATA: callback_query.data,
            ATTR_MSG: None,
            ATTR_CHAT_ID: None,
        }
        if callback_query.message:
            event_data[ATTR_MSG] = callback_query.message.to_dict()
            event_data[ATTR_CHAT_ID] = callback_query.message.chat.id

        if callback_query.from_user:
            event_data.update(self._get_user_event_data(callback_query.from_user))

        # Split data into command and args if possible
        event_data.update(self._get_command_event_data(callback_query.data))

        return event_type, event_data

    def authorize_update(self, update: Update) -> bool:
        """Make sure either user or chat is in allowed_chat_ids."""
        from_user = update.effective_user.id if update.effective_user else None
        from_chat = update.effective_chat.id if update.effective_chat else None
        allowed_chat_ids: list[int] = [
            subentry.data[CONF_CHAT_ID] for subentry in self.config.subentries.values()
        ]
        if from_user in allowed_chat_ids or from_chat in allowed_chat_ids:
            return True
        _LOGGER.error(
            (
                "Unauthorized update - neither user id %s nor chat id %s is in allowed"
                " chats: %s"
            ),
            from_user,
            from_chat,
            allowed_chat_ids,
        )
        return False


class TelegramNotificationService:
    """Implement the notification services for the Telegram Bot domain."""

    def __init__(
        self,
        hass: HomeAssistant,
        app: BaseTelegramBot,
        bot: Bot,
        config: TelegramBotConfigEntry,
        parser: str,
    ) -> None:
        """Initialize the service."""
        self.app = app
        self.config = config
        self._parsers: dict[str, str | None] = {
            PARSER_HTML: ParseMode.HTML,
            PARSER_MD: ParseMode.MARKDOWN,
            PARSER_MD2: ParseMode.MARKDOWN_V2,
            PARSER_PLAIN_TEXT: None,
        }
        self.parse_mode = self._parsers[parser]
        self.bot = bot
        self.hass = hass
        self._last_message_id: dict[int, int] = {}

    def _get_allowed_chat_ids(self) -> list[int]:
        allowed_chat_ids: list[int] = [
            subentry.data[CONF_CHAT_ID] for subentry in self.config.subentries.values()
        ]

        if not allowed_chat_ids:
            bot_name: str = self.config.title
            raise ServiceValidationError(
                "No allowed chat IDs found for bot",
                translation_domain=DOMAIN,
                translation_key="missing_allowed_chat_ids",
                translation_placeholders={
                    "bot_name": bot_name,
                },
            )

        return allowed_chat_ids

    def _get_msg_ids(
        self, msg_data: dict[str, Any], chat_id: int
    ) -> tuple[Any | None, int | None]:
        """Get the message id to edit.

        This can be one of (message_id, inline_message_id) from a msg dict,
        returning a tuple.
        **You can use 'last' as message_id** to edit
        the message last sent in the chat_id.
        """
        message_id: Any | None = None
        inline_message_id: int | None = None
        if ATTR_MESSAGEID in msg_data:
            message_id = msg_data[ATTR_MESSAGEID]
            if (
                isinstance(message_id, str)
                and (message_id == "last")
                and (chat_id in self._last_message_id)
            ):
                message_id = self._last_message_id[chat_id]
        else:
            inline_message_id = msg_data["inline_message_id"]
        return message_id, inline_message_id

    def get_target_chat_ids(self, target: int | list[int] | None) -> list[int]:
        """Validate chat_id targets or return default target (first).

        :param target: optional list of integers ([12234, -12345])
        :return list of chat_id targets (integers)
        """
        allowed_chat_ids: list[int] = self._get_allowed_chat_ids()

        if target is None:
            return [allowed_chat_ids[0]]

        chat_ids = [target] if isinstance(target, int) else target
        valid_chat_ids = [
            chat_id for chat_id in chat_ids if chat_id in allowed_chat_ids
        ]
        if not valid_chat_ids:
            raise ServiceValidationError(
                "Invalid chat IDs",
                translation_domain=DOMAIN,
                translation_key="invalid_chat_ids",
                translation_placeholders={
                    "chat_ids": ", ".join(str(chat_id) for chat_id in chat_ids),
                    "bot_name": self.config.title,
                },
            )
        return valid_chat_ids

    def _get_msg_kwargs(self, data: dict[str, Any]) -> dict[str, Any]:
        """Get parameters in message data kwargs."""

        def _make_row_inline_keyboard(row_keyboard: Any) -> list[InlineKeyboardButton]:
            """Make a list of InlineKeyboardButtons.

            It can accept:
              - a list of tuples like:
                `[(text_b1, data_callback_b1),
                (text_b2, data_callback_b2), ...]
              - a string like: `/cmd1, /cmd2, /cmd3`
              - or a string like: `text_b1:/cmd1, text_b2:/cmd2`
              - also supports urls instead of callback commands
            """
            buttons = []
            if isinstance(row_keyboard, str):
                for key in row_keyboard.split(","):
                    if ":/" in key:
                        # check if command or URL
                        if "https://" in key:
                            label = key.split(":")[0]
                            url = key[len(label) + 1 :]
                            buttons.append(InlineKeyboardButton(label, url=url))
                        else:
                            # commands like: 'Label:/cmd' become ('Label', '/cmd')
                            label = key.split(":/")[0]
                            command = key[len(label) + 1 :]
                            buttons.append(
                                InlineKeyboardButton(label, callback_data=command)
                            )
                    else:
                        # commands like: '/cmd' become ('CMD', '/cmd')
                        label = key.strip()[1:].upper()
                        buttons.append(InlineKeyboardButton(label, callback_data=key))
            elif isinstance(row_keyboard, list):
                for entry in row_keyboard:
                    text_btn, data_btn = entry
                    if data_btn.startswith("https://"):
                        buttons.append(InlineKeyboardButton(text_btn, url=data_btn))
                    else:
                        buttons.append(
                            InlineKeyboardButton(text_btn, callback_data=data_btn)
                        )
            else:
                raise TypeError(str(row_keyboard))
            return buttons

        # Defaults
        params: dict[str, Any] = {
            ATTR_PARSER: self.parse_mode,
            ATTR_DISABLE_NOTIF: False,
            ATTR_DISABLE_WEB_PREV: None,
            ATTR_REPLY_TO_MSGID: None,
            ATTR_REPLYMARKUP: None,
            ATTR_TIMEOUT: None,
            ATTR_MESSAGE_TAG: None,
            ATTR_MESSAGE_THREAD_ID: None,
        }
        if data is not None:
            if ATTR_PARSER in data:
                params[ATTR_PARSER] = data[ATTR_PARSER]
            if ATTR_TIMEOUT in data:
                params[ATTR_TIMEOUT] = data[ATTR_TIMEOUT]
            if ATTR_DISABLE_NOTIF in data:
                params[ATTR_DISABLE_NOTIF] = data[ATTR_DISABLE_NOTIF]
            if ATTR_DISABLE_WEB_PREV in data:
                params[ATTR_DISABLE_WEB_PREV] = data[ATTR_DISABLE_WEB_PREV]
            if ATTR_REPLY_TO_MSGID in data:
                params[ATTR_REPLY_TO_MSGID] = data[ATTR_REPLY_TO_MSGID]
            if ATTR_MESSAGE_TAG in data:
                params[ATTR_MESSAGE_TAG] = data[ATTR_MESSAGE_TAG]
            if ATTR_MESSAGE_THREAD_ID in data:
                params[ATTR_MESSAGE_THREAD_ID] = data[ATTR_MESSAGE_THREAD_ID]
            # Keyboards:
            if ATTR_KEYBOARD in data:
                keys = data.get(ATTR_KEYBOARD)
                keys = keys if isinstance(keys, list) else [keys]
                if keys:
                    params[ATTR_REPLYMARKUP] = ReplyKeyboardMarkup(
                        [[key.strip() for key in row.split(",")] for row in keys],
                        resize_keyboard=data.get(ATTR_RESIZE_KEYBOARD, False),
                        one_time_keyboard=data.get(ATTR_ONE_TIME_KEYBOARD, False),
                    )
                else:
                    params[ATTR_REPLYMARKUP] = ReplyKeyboardRemove(True)

            elif ATTR_KEYBOARD_INLINE in data:
                keys = data.get(ATTR_KEYBOARD_INLINE)
                keys = keys if isinstance(keys, list) else [keys]
                params[ATTR_REPLYMARKUP] = InlineKeyboardMarkup(
                    [_make_row_inline_keyboard(row) for row in keys]
                )
        if params[ATTR_PARSER] == PARSER_PLAIN_TEXT:
            params[ATTR_PARSER] = None
        return params

    async def _send_msg(
        self,
        func_send: Callable,
        msg_error: str,
        message_tag: str | None,
        *args_msg: Any,
        context: Context | None = None,
        **kwargs_msg: Any,
    ) -> Any:
        """Send one message."""
        try:
            out = await func_send(*args_msg, **kwargs_msg)
            if isinstance(out, Message):
                chat_id = out.chat_id
                message_id = out.message_id
                self._last_message_id[chat_id] = message_id
                _LOGGER.debug(
                    "Last message ID: %s (from chat_id %s)",
                    self._last_message_id,
                    chat_id,
                )

                event_data: dict[str, Any] = {
                    ATTR_CHAT_ID: chat_id,
                    ATTR_MESSAGEID: message_id,
                }
                if message_tag is not None:
                    event_data[ATTR_MESSAGE_TAG] = message_tag
                if kwargs_msg.get(ATTR_MESSAGE_THREAD_ID) is not None:
                    event_data[ATTR_MESSAGE_THREAD_ID] = kwargs_msg[
                        ATTR_MESSAGE_THREAD_ID
                    ]

                event_data["bot"] = _get_bot_info(self.bot, self.config)

                self.hass.bus.async_fire(
                    EVENT_TELEGRAM_SENT, event_data, context=context
                )
        except TelegramError as exc:
            _LOGGER.error(
                "%s: %s. Args: %s, kwargs: %s", msg_error, exc, args_msg, kwargs_msg
            )
            return None
        return out

    async def send_message(
        self,
        message: str = "",
        target: Any = None,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> dict[int, int]:
        """Send a message to one or multiple pre-allowed chat IDs."""
        title = kwargs.get(ATTR_TITLE)
        text = f"{title}\n{message}" if title else message
        params = self._get_msg_kwargs(kwargs)
        msg_ids = {}
        for chat_id in self.get_target_chat_ids(target):
            _LOGGER.debug("Send message in chat ID %s with params: %s", chat_id, params)
            msg = await self._send_msg(
                self.bot.send_message,
                "Error sending message",
                params[ATTR_MESSAGE_TAG],
                chat_id,
                text,
                parse_mode=params[ATTR_PARSER],
                disable_web_page_preview=params[ATTR_DISABLE_WEB_PREV],
                disable_notification=params[ATTR_DISABLE_NOTIF],
                reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                reply_markup=params[ATTR_REPLYMARKUP],
                read_timeout=params[ATTR_TIMEOUT],
                message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                context=context,
            )
            if msg is not None:
                msg_ids[chat_id] = msg.id
        return msg_ids

    async def delete_message(
        self,
        chat_id: int | None = None,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> bool:
        """Delete a previously sent message."""
        chat_id = self.get_target_chat_ids(chat_id)[0]
        message_id, _ = self._get_msg_ids(kwargs, chat_id)
        _LOGGER.debug("Delete message %s in chat ID %s", message_id, chat_id)
        deleted: bool = await self._send_msg(
            self.bot.delete_message,
            "Error deleting message",
            None,
            chat_id,
            message_id,
            context=context,
        )
        # reduce message_id anyway:
        if chat_id in self._last_message_id:
            # change last msg_id for deque(n_msgs)?
            self._last_message_id[chat_id] -= 1
        return deleted

    async def edit_message(
        self,
        type_edit: str,
        chat_id: int | None = None,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> Any:
        """Edit a previously sent message."""
        chat_id = self.get_target_chat_ids(chat_id)[0]
        message_id, inline_message_id = self._get_msg_ids(kwargs, chat_id)
        params = self._get_msg_kwargs(kwargs)
        _LOGGER.debug(
            "Edit message %s in chat ID %s with params: %s",
            message_id or inline_message_id,
            chat_id,
            params,
        )
        if type_edit == SERVICE_EDIT_MESSAGE:
            message = kwargs.get(ATTR_MESSAGE)
            title = kwargs.get(ATTR_TITLE)
            text = f"{title}\n{message}" if title else message
            _LOGGER.debug("Editing message with ID %s", message_id or inline_message_id)
            return await self._send_msg(
                self.bot.edit_message_text,
                "Error editing text message",
                params[ATTR_MESSAGE_TAG],
                text,
                chat_id=chat_id,
                message_id=message_id,
                inline_message_id=inline_message_id,
                parse_mode=params[ATTR_PARSER],
                disable_web_page_preview=params[ATTR_DISABLE_WEB_PREV],
                reply_markup=params[ATTR_REPLYMARKUP],
                read_timeout=params[ATTR_TIMEOUT],
                context=context,
            )
        if type_edit == SERVICE_EDIT_CAPTION:
            return await self._send_msg(
                self.bot.edit_message_caption,
                "Error editing message attributes",
                params[ATTR_MESSAGE_TAG],
                chat_id=chat_id,
                message_id=message_id,
                inline_message_id=inline_message_id,
                caption=kwargs.get(ATTR_CAPTION),
                reply_markup=params[ATTR_REPLYMARKUP],
                read_timeout=params[ATTR_TIMEOUT],
                parse_mode=params[ATTR_PARSER],
                context=context,
            )

        return await self._send_msg(
            self.bot.edit_message_reply_markup,
            "Error editing message attributes",
            params[ATTR_MESSAGE_TAG],
            chat_id=chat_id,
            message_id=message_id,
            inline_message_id=inline_message_id,
            reply_markup=params[ATTR_REPLYMARKUP],
            read_timeout=params[ATTR_TIMEOUT],
            context=context,
        )

    async def answer_callback_query(
        self,
        message: str | None,
        callback_query_id: str,
        show_alert: bool = False,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """Answer a callback originated with a press in an inline keyboard."""
        params = self._get_msg_kwargs(kwargs)
        _LOGGER.debug(
            "Answer callback query with callback ID %s: %s, alert: %s",
            callback_query_id,
            message,
            show_alert,
        )
        await self._send_msg(
            self.bot.answer_callback_query,
            "Error sending answer callback query",
            params[ATTR_MESSAGE_TAG],
            callback_query_id,
            text=message,
            show_alert=show_alert,
            read_timeout=params[ATTR_TIMEOUT],
            context=context,
        )

    async def send_chat_action(
        self,
        chat_action: str = "",
        target: Any = None,
        context: Context | None = None,
        **kwargs: Any,
    ) -> dict[int, int]:
        """Send a chat action to a pre-allowed chat ID."""
        chat_id = self.get_target_chat_ids(target)[0]
        _LOGGER.debug("Send action %chat_action in chat ID %s", chat_action, chat_id)
        is_successful = await self._send_msg(
            self.bot.send_chat_action,
            "Error sending action",
            None,
            chat_id=chat_id,
            action=chat_action,
            context=context,
        )
        return {chat_id: is_successful}

    async def send_file(
        self,
        file_type: str,
        target: Any = None,
        context: Context | None = None,
        **kwargs: Any,
    ) -> dict[int, int]:
        """Send a photo, sticker, video, or document."""
        params = self._get_msg_kwargs(kwargs)
        file_content = await load_data(
            self.hass,
            url=kwargs.get(ATTR_URL),
            filepath=kwargs.get(ATTR_FILE),
            username=kwargs.get(ATTR_USERNAME, ""),
            password=kwargs.get(ATTR_PASSWORD, ""),
            authentication=kwargs.get(ATTR_AUTHENTICATION),
            verify_ssl=(
                get_default_context()
                if kwargs.get(ATTR_VERIFY_SSL, False)
                else get_default_no_verify_context()
            ),
        )

        msg_ids = {}
        if file_content:
            for chat_id in self.get_target_chat_ids(target):
                _LOGGER.debug("Sending file to chat ID %s", chat_id)

                if file_type == SERVICE_SEND_PHOTO:
                    msg = await self._send_msg(
                        self.bot.send_photo,
                        "Error sending photo",
                        params[ATTR_MESSAGE_TAG],
                        chat_id=chat_id,
                        photo=file_content,
                        caption=kwargs.get(ATTR_CAPTION),
                        disable_notification=params[ATTR_DISABLE_NOTIF],
                        reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                        reply_markup=params[ATTR_REPLYMARKUP],
                        read_timeout=params[ATTR_TIMEOUT],
                        parse_mode=params[ATTR_PARSER],
                        message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                        context=context,
                    )

                elif file_type == SERVICE_SEND_STICKER:
                    msg = await self._send_msg(
                        self.bot.send_sticker,
                        "Error sending sticker",
                        params[ATTR_MESSAGE_TAG],
                        chat_id=chat_id,
                        sticker=file_content,
                        disable_notification=params[ATTR_DISABLE_NOTIF],
                        reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                        reply_markup=params[ATTR_REPLYMARKUP],
                        read_timeout=params[ATTR_TIMEOUT],
                        message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                        context=context,
                    )

                elif file_type == SERVICE_SEND_VIDEO:
                    msg = await self._send_msg(
                        self.bot.send_video,
                        "Error sending video",
                        params[ATTR_MESSAGE_TAG],
                        chat_id=chat_id,
                        video=file_content,
                        caption=kwargs.get(ATTR_CAPTION),
                        disable_notification=params[ATTR_DISABLE_NOTIF],
                        reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                        reply_markup=params[ATTR_REPLYMARKUP],
                        read_timeout=params[ATTR_TIMEOUT],
                        parse_mode=params[ATTR_PARSER],
                        message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                        context=context,
                    )
                elif file_type == SERVICE_SEND_DOCUMENT:
                    msg = await self._send_msg(
                        self.bot.send_document,
                        "Error sending document",
                        params[ATTR_MESSAGE_TAG],
                        chat_id=chat_id,
                        document=file_content,
                        caption=kwargs.get(ATTR_CAPTION),
                        disable_notification=params[ATTR_DISABLE_NOTIF],
                        reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                        reply_markup=params[ATTR_REPLYMARKUP],
                        read_timeout=params[ATTR_TIMEOUT],
                        parse_mode=params[ATTR_PARSER],
                        message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                        context=context,
                    )
                elif file_type == SERVICE_SEND_VOICE:
                    msg = await self._send_msg(
                        self.bot.send_voice,
                        "Error sending voice",
                        params[ATTR_MESSAGE_TAG],
                        chat_id=chat_id,
                        voice=file_content,
                        caption=kwargs.get(ATTR_CAPTION),
                        disable_notification=params[ATTR_DISABLE_NOTIF],
                        reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                        reply_markup=params[ATTR_REPLYMARKUP],
                        read_timeout=params[ATTR_TIMEOUT],
                        message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                        context=context,
                    )
                elif file_type == SERVICE_SEND_ANIMATION:
                    msg = await self._send_msg(
                        self.bot.send_animation,
                        "Error sending animation",
                        params[ATTR_MESSAGE_TAG],
                        chat_id=chat_id,
                        animation=file_content,
                        caption=kwargs.get(ATTR_CAPTION),
                        disable_notification=params[ATTR_DISABLE_NOTIF],
                        reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                        reply_markup=params[ATTR_REPLYMARKUP],
                        read_timeout=params[ATTR_TIMEOUT],
                        parse_mode=params[ATTR_PARSER],
                        message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                        context=context,
                    )

                msg_ids[chat_id] = msg.id
                file_content.seek(0)
        else:
            _LOGGER.error("Can't send file with kwargs: %s", kwargs)

        return msg_ids

    async def send_sticker(
        self,
        target: Any = None,
        context: Context | None = None,
        **kwargs: Any,
    ) -> dict[int, int]:
        """Send a sticker from a telegram sticker pack."""
        params = self._get_msg_kwargs(kwargs)
        stickerid = kwargs.get(ATTR_STICKER_ID)

        msg_ids = {}
        if stickerid:
            for chat_id in self.get_target_chat_ids(target):
                msg = await self._send_msg(
                    self.bot.send_sticker,
                    "Error sending sticker",
                    params[ATTR_MESSAGE_TAG],
                    chat_id=chat_id,
                    sticker=stickerid,
                    disable_notification=params[ATTR_DISABLE_NOTIF],
                    reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                    reply_markup=params[ATTR_REPLYMARKUP],
                    read_timeout=params[ATTR_TIMEOUT],
                    message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                    context=context,
                )
                msg_ids[chat_id] = msg.id
            return msg_ids
        return await self.send_file(SERVICE_SEND_STICKER, target, context, **kwargs)

    async def send_location(
        self,
        latitude: Any,
        longitude: Any,
        target: Any = None,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> dict[int, int]:
        """Send a location."""
        latitude = float(latitude)
        longitude = float(longitude)
        params = self._get_msg_kwargs(kwargs)
        msg_ids = {}
        for chat_id in self.get_target_chat_ids(target):
            _LOGGER.debug(
                "Send location %s/%s to chat ID %s", latitude, longitude, chat_id
            )
            msg = await self._send_msg(
                self.bot.send_location,
                "Error sending location",
                params[ATTR_MESSAGE_TAG],
                chat_id=chat_id,
                latitude=latitude,
                longitude=longitude,
                disable_notification=params[ATTR_DISABLE_NOTIF],
                reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                read_timeout=params[ATTR_TIMEOUT],
                message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                context=context,
            )
            msg_ids[chat_id] = msg.id
        return msg_ids

    async def send_poll(
        self,
        question: str,
        options: Sequence[str | InputPollOption],
        is_anonymous: bool | None,
        allows_multiple_answers: bool | None,
        target: Any = None,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> dict[int, int]:
        """Send a poll."""
        params = self._get_msg_kwargs(kwargs)
        openperiod = kwargs.get(ATTR_OPEN_PERIOD)
        msg_ids = {}
        for chat_id in self.get_target_chat_ids(target):
            _LOGGER.debug("Send poll '%s' to chat ID %s", question, chat_id)
            msg = await self._send_msg(
                self.bot.send_poll,
                "Error sending poll",
                params[ATTR_MESSAGE_TAG],
                chat_id=chat_id,
                question=question,
                options=options,
                is_anonymous=is_anonymous,
                allows_multiple_answers=allows_multiple_answers,
                open_period=openperiod,
                disable_notification=params[ATTR_DISABLE_NOTIF],
                reply_to_message_id=params[ATTR_REPLY_TO_MSGID],
                read_timeout=params[ATTR_TIMEOUT],
                message_thread_id=params[ATTR_MESSAGE_THREAD_ID],
                context=context,
            )
            msg_ids[chat_id] = msg.id
        return msg_ids

    async def leave_chat(
        self,
        chat_id: int | None = None,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> Any:
        """Remove bot from chat."""
        chat_id = self.get_target_chat_ids(chat_id)[0]
        _LOGGER.debug("Leave from chat ID %s", chat_id)
        return await self._send_msg(
            self.bot.leave_chat, "Error leaving chat", None, chat_id, context=context
        )

    async def set_message_reaction(
        self,
        reaction: str,
        chat_id: int | None = None,
        is_big: bool = False,
        context: Context | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """Set the bot's reaction for a given message."""
        chat_id = self.get_target_chat_ids(chat_id)[0]
        message_id, _ = self._get_msg_ids(kwargs, chat_id)
        params = self._get_msg_kwargs(kwargs)

        _LOGGER.debug(
            "Set reaction to message %s in chat ID %s to %s with params: %s",
            message_id,
            chat_id,
            reaction,
            params,
        )

        await self._send_msg(
            self.bot.set_message_reaction,
            "Error setting message reaction",
            params[ATTR_MESSAGE_TAG],
            chat_id,
            message_id,
            reaction=reaction,
            is_big=is_big,
            read_timeout=params[ATTR_TIMEOUT],
            context=context,
        )


def initialize_bot(hass: HomeAssistant, p_config: MappingProxyType[str, Any]) -> Bot:
    """Initialize telegram bot with proxy support."""
    api_key: str = p_config[CONF_API_KEY]
    proxy_url: str | None = p_config.get(CONF_PROXY_URL)

    if proxy_url is not None:
        proxy = httpx.Proxy(proxy_url)
        request = HTTPXRequest(connection_pool_size=8, proxy=proxy)
    else:
        request = HTTPXRequest(connection_pool_size=8)
    return Bot(token=api_key, request=request)


async def load_data(
    hass: HomeAssistant,
    url: str | None,
    filepath: str | None,
    username: str,
    password: str,
    authentication: str | None,
    verify_ssl: SSLContext,
    num_retries: int = 5,
) -> io.BytesIO:
    """Load data into ByteIO/File container from a source."""
    if url is not None:
        # Load data from URL
        params: dict[str, Any] = {}
        headers: dict[str, str] = {}
        _validate_credentials_input(authentication, username, password)
        if authentication == HTTP_BEARER_AUTHENTICATION:
            headers = {"Authorization": f"Bearer {password}"}
        elif authentication == HTTP_DIGEST_AUTHENTICATION:
            params["auth"] = httpx.DigestAuth(username, password)
        elif authentication == HTTP_BASIC_AUTHENTICATION:
            params["auth"] = httpx.BasicAuth(username, password)

        if verify_ssl is not None:
            params["verify"] = verify_ssl

        retry_num = 0
        async with httpx.AsyncClient(timeout=15, headers=headers, **params) as client:
            while retry_num < num_retries:
                try:
                    req = await client.get(url)
                except (httpx.HTTPError, httpx.InvalidURL) as err:
                    raise HomeAssistantError(
                        f"Failed to load URL: {err!s}",
                        translation_domain=DOMAIN,
                        translation_key="failed_to_load_url",
                        translation_placeholders={"error": str(err)},
                    ) from err

                if req.status_code != 200:
                    _LOGGER.warning(
                        "Status code %s (retry #%s) loading %s",
                        req.status_code,
                        retry_num + 1,
                        url,
                    )
                else:
                    data = io.BytesIO(req.content)
                    if data.read():
                        data.seek(0)
                        data.name = url
                        return data
                    _LOGGER.warning("Empty data (retry #%s) in %s)", retry_num + 1, url)
                retry_num += 1
                if retry_num < num_retries:
                    await asyncio.sleep(
                        1
                    )  # Add a sleep to allow other async operations to proceed
            raise HomeAssistantError(
                f"Failed to load URL: {req.status_code}",
                translation_domain=DOMAIN,
                translation_key="failed_to_load_url",
                translation_placeholders={"error": str(req.status_code)},
            )
    elif filepath is not None:
        if hass.config.is_allowed_path(filepath):
            return await hass.async_add_executor_job(_read_file_as_bytesio, filepath)

        raise ServiceValidationError(
            "File path has not been configured in allowlist_external_dirs.",
            translation_domain=DOMAIN,
            translation_key="allowlist_external_dirs_error",
        )
    else:
        raise ServiceValidationError(
            "URL or File is required.",
            translation_domain=DOMAIN,
            translation_key="missing_input",
            translation_placeholders={"field": "URL or File"},
        )


def _validate_credentials_input(
    authentication: str | None, username: str | None, password: str | None
) -> None:
    if (
        authentication in (HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
        and not username
    ):
        raise ServiceValidationError(
            "Username is required.",
            translation_domain=DOMAIN,
            translation_key="missing_input",
            translation_placeholders={"field": "Username"},
        )

    if (
        authentication
        in (
            HTTP_BASIC_AUTHENTICATION,
            HTTP_BEARER_AUTHENTICATION,
            HTTP_BEARER_AUTHENTICATION,
        )
        and not password
    ):
        raise ServiceValidationError(
            "Password is required.",
            translation_domain=DOMAIN,
            translation_key="missing_input",
            translation_placeholders={"field": "Password"},
        )


def _read_file_as_bytesio(file_path: str) -> io.BytesIO:
    """Read a file and return it as a BytesIO object."""
    try:
        with open(file_path, "rb") as file:
            data = io.BytesIO(file.read())
            data.name = file_path
            return data
    except OSError as err:
        raise HomeAssistantError(
            f"Failed to load file: {err!s}",
            translation_domain=DOMAIN,
            translation_key="failed_to_load_file",
            translation_placeholders={"error": str(err)},
        ) from err
