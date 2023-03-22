"""Constants for Bravia TV integration."""
from __future__ import annotations

from typing import Final

from homeassistant.backports.enum import StrEnum

ATTR_CID: Final = "cid"
ATTR_MAC: Final = "macAddr"
ATTR_MANUFACTURER: Final = "Sony"
ATTR_MODEL: Final = "model"

CONF_CLIENT_ID: Final = "client_id"
CONF_NICKNAME: Final = "nickname"
CONF_USE_PSK: Final = "use_psk"

DOMAIN: Final = "braviatv"
LEGACY_CLIENT_ID: Final = "HomeAssistant"
NICKNAME_PREFIX: Final = "Home Assistant"


class SourceType(StrEnum):
    """Source type for Sony TV Integration."""

    APP = "app"
    CHANNEL = "channel"
    INPUT = "input"
