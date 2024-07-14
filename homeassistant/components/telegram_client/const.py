"""Constants for the Telegram client integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import __version__ as ha_version

# region general
DOMAIN: Final = "telegram_client"
LOGGER: Final = logging.getLogger(__name__)
SCAN_INTERVAL: Final = timedelta(seconds=10)
CLIENT_PARAMS: Final = {
    "device_model": "Home Assistant",
    "system_version": ha_version,
    "app_version": "1.0.0",
}
# endregion

# region client types
CLIENT_TYPE_BOT: Final = "bot"
CLIENT_TYPE_USER: Final = "client"
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
OPTION_BLACKLIST_USERS: Final = "blacklist_users"
OPTION_CHATS: Final = "chats"
OPTION_DATA: Final = "data"
OPTION_EVENTS: Final = "events"
OPTION_FORWARDS: Final = "forwards"
OPTION_FROM_USERS: Final = "from_users"
OPTION_INBOX: Final = "inbox"
OPTION_INCOMING: Final = "incoming"
OPTION_OUTGOING: Final = "outgoing"
OPTION_PATTERN: Final = "pattern"
OPTION_USERS: Final = "users"
# endregion

# region sensors
SENSOR_FIRST_NAME: Final = "first_name"
SENSOR_ID: Final = "id"
SENSOR_LAST_DELETED_MESSAGE_ID: Final = "last_deleted_message_id"
SENSOR_LAST_EDITED_MESSAGE_ID: Final = "last_edited_message_id"
SENSOR_LAST_NAME: Final = "last_name"
SENSOR_LAST_SENT_MESSAGE_ID: Final = "last_sent_message_id"
SENSOR_PHONE: Final = "phone"
SENSOR_PREMIUM: Final = "premium"
SENSOR_RESTRICTED: Final = "restricted"
SENSOR_USERNAME: Final = "username"
# endregion

# region services
SERVICE_DELETE_MESSAGES: Final = "delete_messages"
SERVICE_EDIT_MESSAGE: Final = "edit_message"
SERVICE_SEND_MESSAGES: Final = "send_messages"
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
FIELD_MESSAGE_IDS: Final = "message_ids"
FIELD_NOSOUND_VIDEO: Final = "nosound_video"
FIELD_PARSE_MODE: Final = "parse_mode"
FIELD_REPLY_TO: Final = "reply_to"
FIELD_REVOKE: Final = "revoke"
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
KEY_ACTION: Final = "action"
KEY_ACTION_MESSAGE: Final = "action_message"
KEY_ADDED_BY: Final = "added_by"
KEY_AUDIO: Final = "audio"
KEY_BASE: Final = "base"
KEY_CANCEL: Final = "cancel"
KEY_CHAT: Final = "chat"
KEY_CHAT_ID: Final = "chat_id"
KEY_CHAT_INSTANCE: Final = "chat_instance"
KEY_CONFIG_ENTRY_ID: Final = "config_entry_id"
KEY_CONTACT: Final = "contact"
KEY_CONTENTS: Final = "contents"
KEY_CREATED: Final = "created"
KEY_DATA: Final = "data"
KEY_DATA_MATCH: Final = "data_match"
KEY_DELETED_ID: Final = "deleted_id"
KEY_DELETED_IDS: Final = "deleted_ids"
KEY_DOCUMENT: Final = "document"
KEY_ENTITY: Final = "entity"
KEY_ENTRY_ID: Final = "entry_id"
KEY_GEO: Final = "geo"
KEY_ID: Final = "id"
KEY_INBOX: Final = "inbox"
KEY_INPUT_CHAT: Final = "input_chat"
KEY_INPUT_SENDER: Final = "input_sender"
KEY_INPUT_USER: Final = "input_user"
KEY_INPUT_USERS: Final = "input_users"
KEY_IS_CHANNEL: Final = "is_channel"
KEY_IS_GROUP: Final = "is_group"
KEY_IS_PRIVATE: Final = "is_private"
KEY_KICKED_BY: Final = "kicked_by"
KEY_LAST_SEEN: Final = "last_seen"
KEY_MAX_ID: Final = "max_id"
KEY_ME: Final = "me"
KEY_MESSAGE: Final = "message"
KEY_MESSAGE_ID: Final = "message_id"
KEY_MESSAGE_IDS: Final = "message_ids"
KEY_NEW_PHOTO: Final = "new_photo"
KEY_NEW_PIN: Final = "new_pin"
KEY_NEW_SCORE: Final = "new_score"
KEY_NEW_TITLE: Final = "new_title"
KEY_OFFSET: Final = "offset"
KEY_ONLINE: Final = "online"
KEY_OUTBOX: Final = "outbox"
KEY_PATTERN_MATCH: Final = "pattern_match"
KEY_PHOTO: Final = "photo"
KEY_PLAYING: Final = "playing"
KEY_QUERY: Final = "query"
KEY_RECENTLY: Final = "recently"
KEY_RECORDING: Final = "recording"
KEY_ROUND: Final = "round"
KEY_SENDER: Final = "sender"
KEY_SENDER_ID: Final = "sender_id"
KEY_STATUS: Final = "status"
KEY_STICKER: Final = "sticker"
KEY_SUGGESTED_VALUE: Final = "suggested_value"
KEY_TYPING: Final = "typing"
KEY_UNPIN: Final = "unpin"
KEY_UNTIL: Final = "until"
KEY_UPLOADING: Final = "uploading"
KEY_USER: Final = "user"
KEY_USERS: Final = "users"
KEY_USER_ADDED: Final = "user_added"
KEY_USER_ID: Final = "user_id"
KEY_USER_IDS: Final = "user_ids"
KEY_USER_JOINED: Final = "user_joined"
KEY_USER_KICKED: Final = "user_kicked"
KEY_USER_LEFT: Final = "user_left"
KEY_VIA_INLINE: Final = "via_inline"
KEY_VIDEO: Final = "video"
KEY_WITHIN_MONTHS: Final = "within_months"
KEY_WITHIN_WEEKS: Final = "within_weeks"
# endregion

# region strings
STRING_BOT: Final = "Bot"
STRING_FIRST_NAME: Final = "First name"
STRING_FORWARDS_DEFAULT: Final = "Default (both)"
STRING_FORWARDS_NON_FORWARDS: Final = "Only non-forwards"
STRING_FORWARDS_ONLY_FORWARDS: Final = "Only forwards"
STRING_ID: Final = "ID"
STRING_LAST_DELETED_MESSAGE_ID: Final = "Last deleted message ID"
STRING_LAST_EDITED_MESSAGE_ID: Final = "Last edited message ID"
STRING_LAST_NAME: Final = "Last name"
STRING_LAST_SENT_MESSAGE_ID: Final = "Last sent message ID"
STRING_PHONE: Final = "Phone"
STRING_PREMIUM: Final = "Premium"
STRING_RESTRICTED: Final = "Restricted"
STRING_USER: Final = "User"
STRING_USERNAME: Final = "Username"
# endregion

# region icons
ICON_ID: Final = "mdi:id-card"
ICON_LAST_DELETED_MESSAGE_ID: Final = "mdi:message-minus"
ICON_LAST_EDITED_MESSAGE_ID: Final = "mdi:message-draw"
ICON_LAST_SENT_MESSAGE_ID: Final = "mdi:message-arrow-right"
ICON_PHONE: Final = "mdi:card-account-phone"
ICON_PREMIUM: Final = "mdi:star"
ICON_USERNAME: Final = "mdi:account"
# endregion
