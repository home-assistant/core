"""Telegram client schemas."""

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DEVICE_ID,
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_KEYBOARD,
    ATTR_KEYBOARD_INLINE,
    ATTR_MESSAGE,
    ATTR_MESSAGE_TAG,
    ATTR_ONE_TIME_KEYBOARD,
    ATTR_PARSER,
    ATTR_REPLY_TO_MSGID,
    ATTR_RESIZE_KEYBOARD,
    ATTR_SCHEDULE,
    ATTR_TARGET_ID,
    ATTR_TARGET_USERNAME,
    ATTR_TIMEOUT,
    CONF_API_HASH,
    CONF_API_ID,
    CONF_OTP,
    CONF_PHONE,
)
from .helpers import date_is_in_future, has_only_one_target_kind

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): str,
        vol.Required(CONF_API_HASH): str,
    }
)
STEP_PHONE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): str,
    }
)
STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP): str,
    }
)
STEP_PASSWORD_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

_BASE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_TARGET_USERNAME): cv.string,
        vol.Optional(ATTR_TARGET_ID): int,
        vol.Optional(ATTR_PARSER): cv.string,
        vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
        vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
        vol.Optional(ATTR_RESIZE_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_ONE_TIME_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_KEYBOARD): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
        vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        vol.Optional(ATTR_MESSAGE_TAG): cv.string,
        vol.Optional(ATTR_REPLY_TO_MSGID): cv.positive_int,
        vol.Optional(ATTR_SCHEDULE): vol.All(cv.datetime, date_is_in_future),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    vol.All(
        _BASE_SERVICE_SCHEMA.extend({vol.Required(ATTR_MESSAGE): cv.string}),
        has_only_one_target_kind,
    )
)
