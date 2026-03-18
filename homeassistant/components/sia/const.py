"""Constants for the sia integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

PLATFORMS: Final = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]

DOMAIN: Final = "sia"

ATTR_CODE: Final = "last_code"
ATTR_ZONE: Final = "last_zone"
ATTR_MESSAGE: Final = "last_message"
ATTR_ID: Final = "last_id"
ATTR_TIMESTAMP: Final = "last_timestamp"

TITLE: Final = "SIA Alarm on port {}"
CONF_ACCOUNT: Final = "account"
CONF_ACCOUNTS: Final = "accounts"
CONF_ADDITIONAL_ACCOUNTS: Final = "additional_account"
CONF_ENCRYPTION_KEY: Final = "encryption_key"
CONF_IGNORE_TIMESTAMPS: Final = "ignore_timestamps"
CONF_PING_INTERVAL: Final = "ping_interval"
CONF_ZONES: Final = "zones"

SIA_HUB_ZONE: Final = 0
SIA_EVENT: Final = "sia_event_{}_{}"

KEY_ALARM: Final = "alarm"
KEY_SMOKE: Final = "smoke"
KEY_MOISTURE: Final = "moisture"
KEY_POWER: Final = "power"
KEY_CONNECTIVITY: Final = "connectivity"

PREVIOUS_STATE: Final = "previous_state"
AVAILABILITY_EVENT_CODE: Final = "RP"
