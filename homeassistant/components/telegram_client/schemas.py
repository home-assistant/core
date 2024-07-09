"""Telegram client schemas."""

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CLEAR_DRAFT,
    ATTR_COMMENT_TO,
    ATTR_FILE,
    ATTR_FORCE_DOCUMENT,
    ATTR_INLINE_KEYBOARD,
    ATTR_KEYBOARD,
    ATTR_KEYBOARD_RESIZE,
    ATTR_KEYBOARD_SINGLE_USE,
    ATTR_LINK_PREVIEW,
    ATTR_MESSAGE,
    ATTR_NOSOUND_VIDEO,
    ATTR_PARSE_MODE,
    ATTR_REPLY_TO,
    ATTR_SCHEDULE,
    ATTR_SILENT,
    ATTR_SUPPORTS_STREAMING,
    ATTR_TARGET_ID,
    ATTR_TARGET_USERNAME,
    ATTR_TTL,
    CONF_API_HASH,
    CONF_API_ID,
    CONF_OTP,
    CONF_PHONE,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_TYPE_BOT,
    CONF_TYPE_CLIENT,
)
from .validators import (
    allow_keyboard_if_file_not_defined,
    allow_keyboard_resize_if_keyboard_defined,
    allow_keyboard_single_use_if_keyboard_defined,
    allow_nosound_video_if_file_defined,
    date_is_in_future,
    has_message_if_file_not_defined,
    has_no_more_than_one_keyboard_kind,
    has_one_target_kind,
)

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): cv.string,
        vol.Required(CONF_API_HASH): cv.string,
        vol.Required(CONF_TYPE): vol.In([CONF_TYPE_CLIENT, CONF_TYPE_BOT]),
    }
)
STEP_PHONE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): cv.string,
    }
)


def step_token_data_schema(default_token=None):
    """Step Token data schema."""
    return vol.Schema({vol.Required(CONF_TOKEN, default=default_token): cv.string})


STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP): cv.string,
    }
)


def step_password_data_schema(default_password=None):
    """Step Password data schema."""
    return vol.Schema(
        {vol.Required(CONF_PASSWORD, default=default_password): cv.string}
    )


_BASE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TARGET_USERNAME): cv.string,
        vol.Optional(ATTR_TARGET_ID): int,
        vol.Optional(ATTR_REPLY_TO): cv.positive_int,
        vol.Optional(ATTR_PARSE_MODE): cv.string,
        vol.Optional(ATTR_LINK_PREVIEW): cv.boolean,
        vol.Optional(ATTR_FILE): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_FORCE_DOCUMENT): cv.boolean,
        vol.Optional(ATTR_CLEAR_DRAFT): cv.boolean,
        vol.Optional(ATTR_KEYBOARD): vol.Or(
            vol.All(cv.ensure_list, [[cv.string]]),
            vol.All(cv.ensure_list, [cv.string]),
        ),
        vol.Optional(ATTR_INLINE_KEYBOARD): cv.ensure_list,
        vol.Optional(ATTR_KEYBOARD_RESIZE): cv.boolean,
        vol.Optional(ATTR_KEYBOARD_SINGLE_USE): cv.boolean,
        vol.Optional(ATTR_SILENT): cv.boolean,
        vol.Optional(ATTR_SUPPORTS_STREAMING): cv.boolean,
        vol.Optional(ATTR_SCHEDULE): vol.All(cv.datetime, date_is_in_future),
        vol.Optional(ATTR_COMMENT_TO): cv.positive_int,
        vol.Optional(ATTR_TTL): vol.All(cv.positive_int, vol.Range(min=1, max=60)),
        vol.Optional(ATTR_NOSOUND_VIDEO): cv.boolean,
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    vol.All(
        _BASE_SERVICE_SCHEMA.extend({vol.Optional(ATTR_MESSAGE): cv.string}),
        has_message_if_file_not_defined,
        has_one_target_kind,
        has_no_more_than_one_keyboard_kind,
        allow_keyboard_resize_if_keyboard_defined,
        allow_keyboard_single_use_if_keyboard_defined,
        allow_nosound_video_if_file_defined,
        allow_keyboard_if_file_not_defined,
    )
)
