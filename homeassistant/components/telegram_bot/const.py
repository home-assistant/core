"""Constants for the Telegram Bot integration."""

from enum import StrEnum
from ipaddress import ip_network

DOMAIN = "telegram_bot"


class TelegramBotService(StrEnum):
    """Store keys for Telegram bot services."""

    SEND_MESSAGE = "send_message"
    SEND_CHAT_ACTION = "send_chat_action"
    SEND_PHOTO = "send_photo"
    SEND_MEDIA_GROUP = "send_media_group"
    SEND_STICKER = "send_sticker"
    SEND_ANIMATION = "send_animation"
    SEND_VIDEO = "send_video"
    SEND_VOICE = "send_voice"
    SEND_DOCUMENT = "send_document"
    SEND_LOCATION = "send_location"
    SEND_POLL = "send_poll"
    EDIT_MESSAGE = "edit_message"
    EDIT_MESSAGE_MEDIA = "edit_message_media"
    EDIT_CAPTION = "edit_caption"
    EDIT_REPLYMARKUP = "edit_replymarkup"
    ANSWER_CALLBACK_QUERY = "answer_callback_query"
    DELETE_MESSAGE = "delete_message"
    LEAVE_CHAT = "leave_chat"
    SET_MESSAGE_REACTION = "set_message_reaction"
    DOWNLOAD_FILE = "download_file"
    SEND_MESSAGE_DRAFT = "send_message_draft"


class TelegramBotServiceArgument(StrEnum):
    """Store keys for Telegram bot service arguments."""

    TITLE = "title"
    MESSAGE = "message"
    PARSE_MODE = "parse_mode"
    DISABLE_NOTIFICATION = "disable_notification"
    DISABLE_WEB_PAGE_PREVIEW = "disable_web_page_preview"
    KEYBOARD = "keyboard"
    INLINE_KEYBOARD = "inline_keyboard"
    MESSAGE_TAG = "message_tag"
    REPLY_TO_MESSAGE_ID = "reply_to_message_id"
    MESSAGE_THREAD_ID = "message_thread_id"
    CHAT_ID = "chat_id"
    CHAT_ACTION = "chat_action"
    URL = "url"
    VERIFY_SSL = "verify_ssl"
    AUTHENTICATION = "authentication"
    USERNAME = "username"
    PASSWORD = "password"
    FILE = "file"
    CAPTION = "caption"
    MEDIA = "media"
    PROTECT_CONTENT = "protect_content"
    STICKER_ID = "sticker_id"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    QUESTION = "question"
    OPTIONS = "options"
    IS_ANONYMOUS = "is_anonymous"
    ALLOWS_MULTIPLE_ANSWERS = "allows_multiple_answers"
    OPEN_PERIOD = "open_period"
    MESSAGE_ID = "message_id"
    MEDIA_TYPE = "media_type"
    CALLBACK_QUERY_ID = "callback_query_id"
    SHOW_ALERT = "show_alert"
    REACTION = "reaction"
    IS_BIG = "is_big"
    FILE_ID = "file_id"
    DIRECTORY_PATH = "directory_path"
    FILE_NAME = "file_name"
    DRAFT_ID = "draft_id"
    RESIZE_KEYBOARD = "resize_keyboard"
    ONE_TIME_KEYBOARD = "one_time_keyboard"


class TelegramBotParseMode(StrEnum):
    """Parse modes of the Telegram bot messages."""

    HTML = "html"
    MARKDOWN = "markdown"
    MARKDOWN_V2 = "markdownv2"
    PLAIN_TEXT = "plain_text"


PLATFORM_BROADCAST = "broadcast"
PLATFORM_POLLING = "polling"
PLATFORM_WEBHOOKS = "webhooks"
SECTION_ADDITIONAL_SETTINGS = "additional_settings"
SUBENTRY_TYPE_ALLOWED_CHAT_IDS = "allowed_chat_ids"


CONF_API_ENDPOINT = "api_endpoint"
CONF_PROXY_URL = "proxy_url"
CONF_TRUSTED_NETWORKS = "trusted_networks"

# subentry
CONF_CHAT_ID = "chat_id"

ERROR_FIELD = "error_field"
ERROR_MESSAGE = "error_message"

DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes
DEFAULT_API_ENDPOINT = "https://api.telegram.org"
DEFAULT_TRUSTED_NETWORKS = [ip_network("149.154.160.0/20"), ip_network("91.108.4.0/22")]


SIGNAL_UPDATE_EVENT = "telegram_bot_update_event"


class TelegramBotEvent(StrEnum):
    """Event types fired by the Telegram bot."""

    CALLBACK = "telegram_callback"
    COMMAND = "telegram_command"
    TEXT = "telegram_text"
    ATTACHMENT = "telegram_attachment"
    SENT = "telegram_sent"


class TelegramBotEventData(StrEnum):
    """Keys of the data of the Telegram bot events."""

    BOT = "bot"
    CHAT_ID = "chat_id"
    CHAT_INSTANCE = "chat_instance"
    MESSAGE_THREAD_ID = "message_thread_id"
    ID = "id"
    MESSAGE_ID = "message_id"
    MESSAGE_TAG = "message_tag"
    REPLY_TO_MESSAGE_ID = "reply_to_message_id"
    DATE = "date"
    TEXT = "text"
    MESSAGE = "message"
    DATA = "data"
    COMMAND = "command"
    ARGS = "args"
    FILE_ID = "file_id"
    FILE_NAME = "file_name"
    FILE_MIME_TYPE = "file_mime_type"
    FILE_SIZE = "file_size"
    USER_ID = "user_id"
    FROM_FIRST = "from_first"
    FROM_LAST = "from_last"


class TelegramBotChatAction(StrEnum):
    """Chat actions of the Telegram bot send_chat_action action."""

    TYPING = "typing"
    UPLOAD_PHOTO = "upload_photo"
    RECORD_VIDEO = "record_video"
    UPLOAD_VIDEO = "upload_video"
    RECORD_VOICE = "record_voice"
    UPLOAD_VOICE = "upload_voice"
    UPLOAD_DOCUMENT = "upload_document"
    CHOOSE_STICKER = "choose_sticker"
    FIND_LOCATION = "find_location"
    RECORD_VIDEO_NOTE = "record_video_note"
    UPLOAD_VIDEO_NOTE = "upload_video_note"


ATTR_DISABLE_NOTIF = "disable_notification"
ATTR_DISABLE_WEB_PREV = "disable_web_page_preview"
ATTR_INLINE_MESSAGE_ID = "inline_message_id"
ATTR_PARSER = "parse_mode"
ATTR_REPLY_TO_MSGID = "reply_to_message_id"
ATTR_REPLYMARKUP = "reply_markup"
ATTR_MESSAGE_TAG = "message_tag"
ATTR_MESSAGE_THREAD_ID = "message_thread_id"


class TelegramBotServiceResponse(StrEnum):
    """Keys of the Telegram bot action responses."""

    CHATS = "chats"
    CHAT_ID = "chat_id"
    MESSAGE_ID = "message_id"
    ENTITY_ID = "entity_id"
    FILE_PATH = "file_path"
