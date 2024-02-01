"""Helper functions for Android TV Remote integration."""
from __future__ import annotations

from androidtvremote2 import AndroidTVRemote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_ENABLE_IME, CONF_ENABLE_IME_DEFAULT_VALUE


def create_api(hass: HomeAssistant, host: str, enable_ime: bool) -> AndroidTVRemote:
    """Create an AndroidTVRemote instance."""
    return AndroidTVRemote(
        client_name="Home Assistant",
        certfile=hass.config.path(STORAGE_DIR, "androidtv_remote_cert.pem"),
        keyfile=hass.config.path(STORAGE_DIR, "androidtv_remote_key.pem"),
        host=host,
        loop=hass.loop,
        enable_ime=enable_ime,
    )


def get_enable_ime(entry: ConfigEntry) -> bool:
    """Get value of enable_ime option or its default value."""
    return entry.options.get(CONF_ENABLE_IME, CONF_ENABLE_IME_DEFAULT_VALUE)
