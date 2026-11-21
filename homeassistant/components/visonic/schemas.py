"""Form schemas for Visonic configuration and options."""

import probatio

from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_ARM_CODE_AUTO,
    CONF_ARM_HOME_ENABLED,
    CONF_CLOUD_APP_ID,
    CONF_DOWNLOAD_CODE,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    CONF_RETRY_CONNECTION_COUNT,
    CONF_RETRY_CONNECTION_DELAY,
    CONF_USER_CODE_SLOT,
    DEFAULT_DEVICE_HOST,
    DEFAULT_DEVICE_PORT,
    DEFAULT_PANEL_USER_CODE,
)
from .visonic_types import DeviceType, TriggerAlarmType

PIN_VALIDATOR = probatio.All(str, probatio.Match("[0-9]{4}\\Z"))
DOWNLOAD_CODE_VALIDATOR = probatio.All(str, probatio.Match("(?:[0-9a-fA-F]{4})?\\Z"))
PORT_VALIDATOR = probatio.All(probatio.Port(), probatio.Coerce(str))
ALARM_TYPE_OPTIONS = [
    str(el.name).lower()
    for el in TriggerAlarmType
    if el not in [TriggerAlarmType.NONE, TriggerAlarmType.UNKNOWN]
]

DEVICE_NO_PANEL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TYPE, default=DeviceType.ETHERNET.title()): probatio.In(
            [
                DeviceType.ETHERNET.title(),
                DeviceType.SERIAL.title(),
                DeviceType.CLOUD.title(),
            ]
        ),
    }
)

DEVICE_SCHEMA = DEVICE_NO_PANEL_SCHEMA.extend(
    {probatio.Required(CONF_PANEL_NUMBER, default=0): cv.positive_int}
)

ETHERNET_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_HOST), default=DEFAULT_DEVICE_HOST): str,
        probatio.Required(
            probatio.Secret(CONF_PORT), default=str(DEFAULT_DEVICE_PORT)
        ): PORT_VALIDATOR,
    }
)

CLOUD_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            probatio.Secret(CONF_EXTERNAL_URL), default="visonic.tycomonitor.com"
        ): str,
        probatio.Required(probatio.Secret(CONF_EMAIL), default=""): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD), default=""): str,
    }
)

CLOUD_PANEL_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            probatio.Secret(CONF_CODE), default=DEFAULT_PANEL_USER_CODE
        ): PIN_VALIDATOR,
    }
)


def _validate_user_code_slot(value: float) -> int:
    """Reject fractional user-code slots rather than truncating them."""
    if not value.is_integer():
        raise probatio.Invalid("User-code slot must be a whole number")
    return int(value)


POWERLINK_SCHEMA = probatio.Schema(
    {
        probatio.Optional(probatio.Secret(CONF_DOWNLOAD_CODE)): DOWNLOAD_CODE_VALIDATOR,
        probatio.Required(CONF_USER_CODE_SLOT, default=1): probatio.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=48, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            probatio.Coerce(_validate_user_code_slot),
        ),
    }
)

_CONNECTION_IDENTITY = {
    probatio.Required(CONF_TYPE): probatio.In(list(DeviceType)),
    probatio.Required(CONF_PANEL_NUMBER): cv.positive_int,
}
_POWERLINK_CONFIG = {
    probatio.Optional(marker.schema): validator
    for marker, validator in POWERLINK_SCHEMA.schema.items()
}

CONNECTION_SCHEMA = probatio.TaggedUnion(
    CONF_TYPE,
    {
        DeviceType.ETHERNET: ETHERNET_SCHEMA.extend(
            {
                **_CONNECTION_IDENTITY,
                **_POWERLINK_CONFIG,
                probatio.Required(probatio.Secret(CONF_HOST)): str,
                probatio.Required(probatio.Secret(CONF_PORT)): PORT_VALIDATOR,
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        DeviceType.SERIAL: probatio.Schema(
            {
                **_CONNECTION_IDENTITY,
                **_POWERLINK_CONFIG,
                probatio.Required(CONF_DEVICE): str,
            },
            extra=probatio.ALLOW_EXTRA,
        ),
        DeviceType.CLOUD: CLOUD_SCHEMA.extend(
            {
                **_CONNECTION_IDENTITY,
                probatio.Required(probatio.Secret(CONF_EXTERNAL_URL)): str,
                probatio.Required(probatio.Secret(CONF_EMAIL)): str,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                probatio.Required(probatio.Secret(CONF_CODE)): PIN_VALIDATOR,
                probatio.Required(probatio.Secret(CONF_PANEL_SERIAL)): str,
                probatio.Required(CONF_CLOUD_APP_ID): str,
            },
            extra=probatio.ALLOW_EXTRA,
        ),
    },
)

CONNECTION_OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_RETRY_CONNECTION_COUNT, default=1
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=1000000, mode=selector.NumberSelectorMode.BOX
            )
        ),
        probatio.Optional(
            CONF_RETRY_CONNECTION_DELAY, default=90
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=5, max=1000, mode=selector.NumberSelectorMode.BOX
            )
        ),
    }
)

ALARM_OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_ARM_CODE_AUTO, default=False): bool,
        probatio.Optional(CONF_ARM_HOME_ENABLED, default=True): bool,
        probatio.Optional(CONF_INSTANT_ARM_AWAY, default=False): bool,
        probatio.Optional(CONF_INSTANT_ARM_HOME, default=False): bool,
        probatio.Optional(CONF_ENABLE_REMOTE_ARM, default=False): bool,
        probatio.Optional(CONF_ENABLE_REMOTE_DISARM, default=False): bool,
    }
)

CLOUD_ALARM_OPTIONS_SCHEMA = probatio.Schema(
    {
        marker: validator
        for marker, validator in ALARM_OPTIONS_SCHEMA.schema.items()
        if marker.schema
        not in {CONF_ARM_CODE_AUTO, CONF_INSTANT_ARM_AWAY, CONF_INSTANT_ARM_HOME}
    }
)
