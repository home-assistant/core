"""The Ring constants."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

ATTRIBUTION = "Data provided by Ring.com"

NOTIFICATION_ID = "ring_notification"
NOTIFICATION_TITLE = "Ring Setup"

DOMAIN = "ring"
DEFAULT_ENTITY_NAMESPACE = "ring"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]


SCAN_INTERVAL = timedelta(minutes=1)

CONF_2FA = "2fa"
CONF_LISTEN_CREDENTIALS = "listen_token"

CONF_CONFIG_ENTRY_MINOR_VERSION: Final = 2
