"""Platform for the Aladdin Connect cover component."""
from __future__ import annotations

from typing import Final

from homeassistant.components.cover import SUPPORT_CLOSE, SUPPORT_OPEN
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

NOTIFICATION_ID: Final = "aladdin_notification"
NOTIFICATION_TITLE: Final = "Aladdin Connect Cover Setup"

STATES_MAP: Final[dict[str, str]] = {
    "open": STATE_OPEN,
    "opening": STATE_OPENING,
    "closed": STATE_CLOSED,
    "closing": STATE_CLOSING,
}

SUPPORTED_FEATURES: Final = SUPPORT_OPEN | SUPPORT_CLOSE
