"""Constants for the Telegram Bot integration."""

PLATFORM_BROADCAST = "broadcast"
PLATFORM_POLLING = "polling"
PLATFORM_WEBHOOKS = "webhooks"

CONF_BOT_COUNT = "bot_count"

ISSUE_DEPRECATED_YAML = "deprecated_yaml"
ISSUE_DEPRECATED_YAML_HAS_MORE_PLATFORMS = (
    "deprecated_yaml_import_issue_has_more_platforms"
)

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
