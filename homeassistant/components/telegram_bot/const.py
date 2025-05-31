"""Constants for the Telegram Bot integration."""

from ipaddress import ip_network

DOMAIN = "telegram_bot"

PLATFORM_BROADCAST = "broadcast"
PLATFORM_POLLING = "polling"
PLATFORM_WEBHOOKS = "webhooks"

SUBENTRY_TYPE_ALLOWED_CHAT_IDS = "allowed_chat_ids"

CONF_BOT_COUNT = "bot_count"
CONF_ALLOWED_CHAT_IDS = "allowed_chat_ids"
CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_PROXY_PARAMS = "proxy_params"


CONF_PROXY_URL = "proxy_url"
CONF_TRUSTED_NETWORKS = "trusted_networks"

# subentry
CONF_CHAT_ID = "chat_id"

BOT_NAME = "telegram_bot"
ERROR_FIELD = "error_field"
ERROR_MESSAGE = "error_message"

ISSUE_DEPRECATED_YAML = "deprecated_yaml"
ISSUE_DEPRECATED_YAML_HAS_MORE_PLATFORMS = (
    "deprecated_yaml_import_issue_has_more_platforms"
)
ISSUE_DEPRECATED_YAML_IMPORT_ISSUE_ERROR = "deprecated_yaml_import_issue_error"

DEFAULT_TRUSTED_NETWORKS = [ip_network("149.154.160.0/20"), ip_network("91.108.4.0/22")]

SERVICE_SEND_MESSAGE = "send_message"
SERVICE_SEND_PHOTO = "send_photo"
SERVICE_SEND_STICKER = "send_sticker"
SERVICE_SEND_ANIMATION = "send_animation"
SERVICE_SEND_VIDEO = "send_video"
SERVICE_SEND_VOICE = "send_voice"
SERVICE_SEND_DOCUMENT = "send_document"
SERVICE_SEND_LOCATION = "send_location"
SERVICE_SEND_POLL = "send_poll"
SERVICE_EDIT_MESSAGE = "edit_message"
SERVICE_EDIT_CAPTION = "edit_caption"
SERVICE_EDIT_REPLYMARKUP = "edit_replymarkup"
SERVICE_ANSWER_CALLBACK_QUERY = "answer_callback_query"
SERVICE_DELETE_MESSAGE = "delete_message"
SERVICE_LEAVE_CHAT = "leave_chat"

EVENT_TELEGRAM_CALLBACK = "telegram_callback"
EVENT_TELEGRAM_COMMAND = "telegram_command"
EVENT_TELEGRAM_TEXT = "telegram_text"
EVENT_TELEGRAM_SENT = "telegram_sent"

PARSER_HTML = "html"
PARSER_MD = "markdown"
PARSER_MD2 = "markdownv2"
PARSER_PLAIN_TEXT = "plain_text"

ATTR_DATA = "data"
ATTR_MESSAGE = "message"
ATTR_TITLE = "title"

ATTR_ARGS = "args"
ATTR_AUTHENTICATION = "authentication"
ATTR_CALLBACK_QUERY = "callback_query"
ATTR_CALLBACK_QUERY_ID = "callback_query_id"
ATTR_CAPTION = "caption"
ATTR_CHAT_ID = "chat_id"
ATTR_CHAT_INSTANCE = "chat_instance"
ATTR_DATE = "date"
ATTR_DISABLE_NOTIF = "disable_notification"
ATTR_DISABLE_WEB_PREV = "disable_web_page_preview"
ATTR_EDITED_MSG = "edited_message"
ATTR_FILE = "file"
ATTR_FROM_FIRST = "from_first"
ATTR_FROM_LAST = "from_last"
ATTR_KEYBOARD = "keyboard"
ATTR_RESIZE_KEYBOARD = "resize_keyboard"
ATTR_ONE_TIME_KEYBOARD = "one_time_keyboard"
ATTR_KEYBOARD_INLINE = "inline_keyboard"
ATTR_MESSAGEID = "message_id"
ATTR_MSG = "message"
ATTR_MSGID = "id"
ATTR_PARSER = "parse_mode"
ATTR_PASSWORD = "password"
ATTR_REPLY_TO_MSGID = "reply_to_message_id"
ATTR_REPLYMARKUP = "reply_markup"
ATTR_SHOW_ALERT = "show_alert"
ATTR_STICKER_ID = "sticker_id"
ATTR_TARGET = "target"
ATTR_TEXT = "text"
ATTR_URL = "url"
ATTR_USER_ID = "user_id"
ATTR_USERNAME = "username"
ATTR_VERIFY_SSL = "verify_ssl"
ATTR_TIMEOUT = "timeout"
ATTR_MESSAGE_TAG = "message_tag"
ATTR_CHANNEL_POST = "channel_post"
ATTR_QUESTION = "question"
ATTR_OPTIONS = "options"
ATTR_ANSWERS = "answers"
ATTR_OPEN_PERIOD = "open_period"
ATTR_IS_ANONYMOUS = "is_anonymous"
ATTR_ALLOWS_MULTIPLE_ANSWERS = "allows_multiple_answers"
ATTR_MESSAGE_THREAD_ID = "message_thread_id"
