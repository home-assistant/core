"""Helper functions for Android TV Remote integration."""
from __future__ import annotations

from androidtvremote2 import AndroidTVRemote

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR


def create_api(hass: HomeAssistant, host: str) -> AndroidTVRemote:
    """Create an AndroidTVRemote instance."""
    return AndroidTVRemote(
        client_name="Home Assistant",
        certfile=hass.config.path(STORAGE_DIR, "androidtv_remote_cert.pem"),
        keyfile=hass.config.path(STORAGE_DIR, "androidtv_remote_key.pem"),
        host=host,
        loop=hass.loop,
    )
