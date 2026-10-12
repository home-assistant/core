"""Const for IFTTT."""

from homeassistant.util.hass_dict import HassKey

DOMAIN = "ifttt"

DATA_API_KEYS: HassKey[dict[str, str]] = HassKey(DOMAIN)

ATTR_EVENT = "event"
ATTR_TARGET = "target"
ATTR_VALUE1 = "value1"
ATTR_VALUE2 = "value2"
ATTR_VALUE3 = "value3"

SERVICE_PUSH_ALARM_STATE = "push_alarm_state"
SERVICE_TRIGGER = "trigger"
