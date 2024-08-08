"""Services, config and options flow schemas."""

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CLIENT_TYPE_BOT,
    CLIENT_TYPE_USER,
    CONF_API_HASH,
    CONF_API_ID,
    CONF_CLIENT_TYPE,
    CONF_OTP,
    CONF_PHONE,
    CONF_TOKEN,
    DOMAIN,
    EVENT_CALLBACK_QUERY,
    EVENT_CHAT_ACTION,
    EVENT_INLINE_QUERY,
    EVENT_MESSAGE_DELETED,
    EVENT_MESSAGE_EDITED,
    EVENT_MESSAGE_READ,
    EVENT_NEW_MESSAGE,
    EVENT_USER_UPDATE,
    FIELD_CLEAR_DRAFT,
    FIELD_COMMENT_TO,
    FIELD_FILE,
    FIELD_FORCE_DOCUMENT,
    FIELD_INLINE_KEYBOARD,
    FIELD_KEYBOARD,
    FIELD_KEYBOARD_RESIZE,
    FIELD_KEYBOARD_SINGLE_USE,
    FIELD_LINK_PREVIEW,
    FIELD_MESSAGE,
    FIELD_MESSAGE_IDS,
    FIELD_NOSOUND_VIDEO,
    FIELD_PARSE_MODE,
    FIELD_REPLY_TO,
    FIELD_REVOKE,
    FIELD_SCHEDULE,
    FIELD_SILENT,
    FIELD_SUPPORTS_STREAMING,
    FIELD_TARGET_ID,
    FIELD_TARGET_USERNAME,
    FIELD_TEXT,
    KEY_CONFIG_ENTRY_ID,
    KEY_SUGGESTED_VALUE,
    OPTION_BLACKLIST_CHATS,
    OPTION_BLACKLIST_USERS,
    OPTION_CHATS,
    OPTION_DATA,
    OPTION_FORWARDS,
    OPTION_FROM_USERS,
    OPTION_INBOX,
    OPTION_INCOMING,
    OPTION_OUTGOING,
    OPTION_PATTERN,
    OPTION_USERS,
    STRING_BOT,
    STRING_FORWARDS_DEFAULT,
    STRING_FORWARDS_NON_FORWARDS,
    STRING_FORWARDS_ONLY_FORWARDS,
    STRING_USER,
)
from .validators import (
    allow_keyboard_if_file_not_defined,
    allow_keyboard_resize_if_keyboard_defined,
    allow_keyboard_single_use_if_keyboard_defined,
    allow_nosound_video_if_file_defined,
    date_is_in_future,
    has_at_least_one_target_kind,
    has_message_if_file_not_defined,
    has_no_more_than_one_keyboard_kind,
    has_one_target_kind,
    string_number,
)

FORWARDS_OPTIONS = {
    None: STRING_FORWARDS_DEFAULT,
    True: STRING_FORWARDS_ONLY_FORWARDS,
    False: STRING_FORWARDS_NON_FORWARDS,
}

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): cv.string,
        vol.Required(CONF_API_HASH): cv.string,
        vol.Required(CONF_CLIENT_TYPE): vol.In(
            {CLIENT_TYPE_USER: STRING_USER, CLIENT_TYPE_BOT: STRING_BOT}
        ),
    }
)
STEP_PHONE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): cv.string,
    }
)


def step_token_data_schema(default_token=None):
    """Handle bot token step data validation."""
    return vol.Schema({vol.Required(CONF_TOKEN, default=default_token): cv.string})


STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP): cv.string,
    }
)


def step_password_data_schema(default_password=None):
    """Handle password step data validation."""
    return vol.Schema(
        {vol.Required(CONF_PASSWORD, default=default_password): cv.string}
    )


def step_events_data_schema(data):
    """Handle events step data validation."""
    return vol.Schema(
        {
            vol.Required(
                EVENT_NEW_MESSAGE,
                default=data.get(EVENT_NEW_MESSAGE, True),
            ): cv.boolean,
            vol.Required(
                EVENT_MESSAGE_EDITED,
                default=data.get(EVENT_MESSAGE_EDITED, True),
            ): cv.boolean,
            vol.Required(
                EVENT_MESSAGE_READ,
                default=data.get(EVENT_MESSAGE_READ, True),
            ): cv.boolean,
            vol.Required(
                EVENT_MESSAGE_DELETED,
                default=data.get(EVENT_MESSAGE_DELETED, True),
            ): cv.boolean,
            vol.Required(
                EVENT_CALLBACK_QUERY,
                default=data.get(EVENT_CALLBACK_QUERY, True),
            ): cv.boolean,
            vol.Required(
                EVENT_INLINE_QUERY,
                default=data.get(EVENT_INLINE_QUERY, True),
            ): cv.boolean,
            vol.Required(
                EVENT_CHAT_ACTION,
                default=data.get(EVENT_CHAT_ACTION, True),
            ): cv.boolean,
            vol.Required(
                EVENT_USER_UPDATE,
                default=data.get(EVENT_USER_UPDATE, True),
            ): cv.boolean,
        }
    )


def step_new_message_data_schema(data):
    """Handle new message step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_INCOMING,
                default=data.get(OPTION_INCOMING, True),
            ): cv.boolean,
            vol.Required(
                OPTION_OUTGOING,
                default=data.get(OPTION_OUTGOING, True),
            ): cv.boolean,
            vol.Required(
                OPTION_FORWARDS,
                default=data.get(OPTION_FORWARDS),
            ): vol.In(FORWARDS_OPTIONS),
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
            vol.Optional(
                OPTION_FROM_USERS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_FROM_USERS, "")},
            ): cv.string,
            vol.Optional(
                OPTION_PATTERN,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_PATTERN, "")},
            ): cv.string,
        }
    )


def step_message_edited_data_schema(data):
    """Handle message edited step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_INCOMING,
                default=data.get(OPTION_INCOMING, True),
            ): cv.boolean,
            vol.Required(
                OPTION_OUTGOING,
                default=data.get(OPTION_OUTGOING, True),
            ): cv.boolean,
            vol.Required(
                OPTION_FORWARDS,
                default=data.get(OPTION_FORWARDS),
            ): vol.In(FORWARDS_OPTIONS),
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
            vol.Optional(
                OPTION_FROM_USERS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_FROM_USERS, "")},
            ): cv.string,
            vol.Optional(
                OPTION_PATTERN,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_PATTERN, "")},
            ): cv.string,
        }
    )


def step_message_read_data_schema(data):
    """Handle message read step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_INBOX,
                default=data.get(OPTION_INBOX, False),
            ): cv.boolean,
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
        }
    )


def step_message_deleted_data_schema(data):
    """Handle message deleted step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
        }
    )


def step_callback_query_data_schema(data):
    """Handle callback query step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
            vol.Optional(
                OPTION_DATA,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_DATA, "")},
            ): cv.string,
            vol.Optional(
                OPTION_PATTERN,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_PATTERN, "")},
            ): cv.string,
        }
    )


def step_inline_query_data_schema(data):
    """Handle inline query step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_BLACKLIST_USERS,
                default=data.get(OPTION_BLACKLIST_USERS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_USERS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_USERS, "")},
            ): cv.string,
            vol.Optional(
                OPTION_PATTERN,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_PATTERN, "")},
            ): cv.string,
        }
    )


def step_chat_action_data_schema(data):
    """Handle chat action step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
        }
    )


def step_user_update_data_schema(data):
    """Handle user update step data validation."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_BLACKLIST_CHATS,
                default=data.get(OPTION_BLACKLIST_CHATS, False),
            ): cv.boolean,
            vol.Optional(
                OPTION_CHATS,
                description={KEY_SUGGESTED_VALUE: data.get(OPTION_CHATS, "")},
            ): cv.string,
        }
    )


SERVICE_SEND_MESSAGES_SCHEMA = vol.Schema(
    vol.All(
        vol.Schema(
            {
                vol.Optional(KEY_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Optional(FIELD_TARGET_USERNAME): cv.ensure_list_csv,
                vol.Optional(FIELD_TARGET_ID): vol.All(
                    cv.ensure_list_csv, [string_number]
                ),
                vol.Required(FIELD_MESSAGE): cv.string,
                vol.Optional(FIELD_REPLY_TO): cv.positive_int,
                vol.Optional(FIELD_PARSE_MODE): cv.string,
                vol.Optional(FIELD_LINK_PREVIEW): cv.boolean,
                vol.Optional(FIELD_FILE): vol.All(cv.ensure_list, [cv.path]),
                vol.Optional(FIELD_FORCE_DOCUMENT): cv.boolean,
                vol.Optional(FIELD_CLEAR_DRAFT): cv.boolean,
                vol.Optional(FIELD_KEYBOARD): vol.Or(
                    vol.All(cv.ensure_list, [[cv.string]]),
                    vol.All(cv.ensure_list, [cv.string]),
                ),
                vol.Optional(FIELD_INLINE_KEYBOARD): cv.ensure_list,
                vol.Optional(FIELD_KEYBOARD_RESIZE): cv.boolean,
                vol.Optional(FIELD_KEYBOARD_SINGLE_USE): cv.boolean,
                vol.Optional(FIELD_SILENT): cv.boolean,
                vol.Optional(FIELD_SUPPORTS_STREAMING): cv.boolean,
                vol.Optional(FIELD_SCHEDULE): vol.All(cv.datetime, date_is_in_future),
                vol.Optional(FIELD_COMMENT_TO): cv.positive_int,
                vol.Optional(FIELD_NOSOUND_VIDEO): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        has_at_least_one_target_kind,
        has_no_more_than_one_keyboard_kind,
        allow_keyboard_resize_if_keyboard_defined,
        allow_keyboard_single_use_if_keyboard_defined,
        allow_keyboard_if_file_not_defined,
    )
)

SERVICE_EDIT_MESSAGE_SCHEMA = vol.Schema(
    vol.All(
        vol.Schema(
            {
                vol.Optional(KEY_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Optional(FIELD_TARGET_USERNAME): cv.string,
                vol.Optional(FIELD_TARGET_ID): int,
                vol.Optional(FIELD_MESSAGE): cv.positive_int,
                vol.Optional(FIELD_TEXT): cv.string,
                vol.Optional(FIELD_PARSE_MODE): cv.string,
                vol.Optional(FIELD_LINK_PREVIEW): cv.boolean,
                vol.Optional(FIELD_FILE): vol.All(cv.ensure_list_csv, [cv.path]),
                vol.Optional(FIELD_FORCE_DOCUMENT): cv.boolean,
                vol.Optional(FIELD_KEYBOARD): vol.Or(
                    vol.All(cv.ensure_list, [[cv.string]]),
                    vol.All(cv.ensure_list, [cv.string]),
                ),
                vol.Optional(FIELD_INLINE_KEYBOARD): cv.ensure_list,
                vol.Optional(FIELD_KEYBOARD_RESIZE): cv.boolean,
                vol.Optional(FIELD_KEYBOARD_SINGLE_USE): cv.boolean,
                vol.Optional(FIELD_SUPPORTS_STREAMING): cv.boolean,
                vol.Optional(FIELD_SCHEDULE): vol.All(cv.datetime, date_is_in_future),
            },
            extra=vol.ALLOW_EXTRA,
        ),
        has_message_if_file_not_defined,
        has_one_target_kind,
        has_no_more_than_one_keyboard_kind,
        allow_keyboard_resize_if_keyboard_defined,
        allow_keyboard_single_use_if_keyboard_defined,
        allow_nosound_video_if_file_defined,
        allow_keyboard_if_file_not_defined,
    )
)

SERVICE_DELETE_MESSAGES_SCHEMA = vol.Schema(
    vol.All(
        vol.Schema(
            {
                vol.Optional(KEY_CONFIG_ENTRY_ID): selector.ConfigEntrySelector(
                    {
                        "integration": DOMAIN,
                    }
                ),
                vol.Optional(FIELD_TARGET_USERNAME): cv.ensure_list_csv,
                vol.Optional(FIELD_TARGET_ID): vol.All(
                    cv.ensure_list_csv, [string_number]
                ),
                vol.Required(FIELD_MESSAGE_IDS): vol.All(
                    cv.ensure_list_csv, [string_number]
                ),
                vol.Optional(FIELD_REVOKE): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
)
