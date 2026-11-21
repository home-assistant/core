"""The aquostv component."""

import sharp_aquos_rc

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.MEDIA_PLAYER]

type AquosConfigEntry = ConfigEntry[sharp_aquos_rc.TV]


async def async_setup_entry(hass: HomeAssistant, entry: AquosConfigEntry) -> None:
    """Set up Sharp Aquos TV from a config entry."""
    entry.runtime_data = sharp_aquos_rc.TV(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        15,
        1,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AquosConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
