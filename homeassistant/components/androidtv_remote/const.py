"""Constants for the Android TV Remote integration."""

from __future__ import annotations

from typing import Final

from androidtvremote2 import AndroidTVRemote

from homeassistant.config_entries import ConfigEntry

DOMAIN: Final = "androidtv_remote"

CONF_APPS = "apps"
CONF_ENABLE_IME: Final = "enable_ime"
CONF_ENABLE_IME_DEFAULT_VALUE: Final = True
CONF_APP_NAME = "app_name"
CONF_APP_ICON = "app_icon"

AndroidTVRemoteConfigEntry = ConfigEntry[AndroidTVRemote]
