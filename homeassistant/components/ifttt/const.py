"""Const for IFTTT."""

from enum import StrEnum

from homeassistant.util.hass_dict import HassKey

DOMAIN = "ifttt"

DATA_API_KEYS: HassKey[dict[str, str]] = HassKey(DOMAIN)

DATA_IFTTT_ALARM = "ifttt_alarm"


class IftttService(StrEnum):
    """Store keys for IFTTT services."""

    PUSH_ALARM_STATE = "push_alarm_state"
    TRIGGER = "trigger"


class IftttServiceArgument(StrEnum):
    """Store keys for IFTTT service arguments."""

    STATE = "state"
    EVENT = "event"
    TARGET = "target"
    VALUE1 = "value1"
    VALUE2 = "value2"
    VALUE3 = "value3"
