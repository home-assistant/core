"""Constants for the Telegram client integration."""

from datetime import timedelta
import logging
from typing import Final

# region general
DOMAIN: Final = "telegram_client"
LOGGER: Final = logging.getLogger(__name__)
SCAN_INTERVAL: Final = timedelta(seconds=10)
# endregion

# region client types
CLIENT_TYPE_BOT: Final = "bot"
CLIENT_TYPE_CLIENT: Final = "client"
# endregion

# region configuration
CONF_API_HASH: Final = "api_hash"
CONF_API_ID: Final = "api_id"
CONF_CLIENT_TYPE: Final = "client_type"
CONF_OTP: Final = "otp"
CONF_PHONE: Final = "phone"
CONF_SESSION_ID: Final = "session_id"
CONF_TOKEN: Final = "token"
# endregion

# region events
EVENT_CALLBACK_QUERY: Final = "callback_query"
EVENT_CHAT_ACTION: Final = "chat_action"
EVENT_INLINE_QUERY: Final = "inline_query"
EVENT_MESSAGE_DELETED: Final = "message_deleted"
EVENT_MESSAGE_EDITED: Final = "message_edited"
EVENT_MESSAGE_READ: Final = "message_read"
EVENT_NEW_MESSAGE: Final = "new_message"
EVENT_USER_UPDATE: Final = "user_update"
# endregion

# region options
OPTION_BLACKLIST_CHATS: Final = "blacklist_chats"
OPTION_CHATS: Final = "chats"
OPTION_DATA: Final = "data"
OPTION_EVENTS: Final = "events"
OPTION_FORWARDS: Final = "forwards"
OPTION_FROM_USERS: Final = "from_users"
OPTION_INBOX: Final = "inbox"
OPTION_INCOMING: Final = "incoming"
OPTION_OUTGOING: Final = "outgoing"
OPTION_PATTERN: Final = "pattern"
# endregion

# region sensors
SENSOR_FIRST_NAME: Final = "first_name"
SENSOR_LAST_EDITED_MESSAGE_ID: Final = "last_edited_message_id"
SENSOR_LAST_NAME: Final = "last_name"
SENSOR_LAST_SENT_MESSAGE_ID: Final = "last_sent_message_id"
SENSOR_PHONE: Final = "phone"
SENSOR_PREMIUM: Final = "premium"
SENSOR_RESTRICTED: Final = "restricted"
SENSOR_USERNAME: Final = "username"
SENSOR_USER_ID: Final = "user_id"
# endregion

# region services
SERVICE_EDIT_MESSAGE: Final = "edit_message"
SERVICE_SEND_MESSAGE: Final = "send_message"
# endregion

# region service fields
FIELD_BUTTONS: Final = "buttons"
FIELD_CLEAR_DRAFT: Final = "clear_draft"
FIELD_COMMENT_TO: Final = "comment_to"
FIELD_FILE: Final = "file"
FIELD_FORCE_DOCUMENT: Final = "force_document"
FIELD_INLINE_KEYBOARD: Final = "inline_keyboard"
FIELD_KEYBOARD: Final = "keyboard"
FIELD_KEYBOARD_RESIZE: Final = "keyboard_resize"
FIELD_KEYBOARD_SINGLE_USE: Final = "keyboard_single_use"
FIELD_LINK_PREVIEW: Final = "link_preview"
FIELD_MESSAGE: Final = "message"
FIELD_NOSOUND_VIDEO: Final = "nosound_video"
FIELD_PARSE_MODE: Final = "parse_mode"
FIELD_REPLY_TO: Final = "reply_to"
FIELD_SCHEDULE: Final = "schedule"
FIELD_SILENT: Final = "silent"
FIELD_SUPPORTS_STREAMING: Final = "supports_streaming"
FIELD_TARGET_ID: Final = "target_id"
FIELD_TARGET_USERNAME: Final = "target_username"
FIELD_TEXT: Final = "text"
FIELD_USERNAME: Final = "username"
FIELD_USER_ID: Final = "user_id"
# endregion

# region keys
KEY_BASE: Final = "base"
KEY_CLIENT: Final = "client"
KEY_ENTRY_ID: Final = "entry_id"
KEY_SUGGESTED_VALUE: Final = "suggested_value"
# endregion

# region strings
STRING_FIRST_NAME: Final = "First name"
STRING_FORWARDS_DEFAULT: Final = "Default (both)"
STRING_FORWARDS_ONLY_FORWARDS: Final = "Only forwards"
STRING_FORWARDS_NON_FORWARDS: Final = "Only non-forwards"
STRING_LAST_EDITED_MESSAGE_ID: Final = "Last edited message ID"
STRING_LAST_NAME: Final = "Last name"
STRING_LAST_SENT_MESSAGE_ID: Final = "Last sent message ID"
STRING_PHONE: Final = "Phone"
STRING_PREMIUM: Final = "Premium"
STRING_RESTRICTED: Final = "Restricted"
STRING_USERNAME: Final = "Username"
STRING_USER_ID: Final = "User ID"
# endregion

# region icons
ICON_LAST_EDITED_MESSAGE_ID: Final = "mdi:message-draw"
ICON_LAST_SENT_MESSAGE_ID: Final = "mdi:message-arrow-right"
ICON_PHONE: Final = "mdi:card-account-phone"
ICON_PREMIUM: Final = "mdi:star"
ICON_USERNAME: Final = "mdi:account"
ICON_USER_ID: Final = "mdi:id-card"
# endregion
