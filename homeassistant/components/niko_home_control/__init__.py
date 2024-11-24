"""The Niko home control integration."""

from __future__ import annotations

from nclib.errors import NetcatError
from nikohomecontrol import NikoHomeControlConnection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS: list[Platform] = [Platform.LIGHT]

type NikoHomeControlConfigEntry = ConfigEntry[NikoHomeControlConnection]


async def async_setup_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Set Niko Home Control from a config entry."""
    try:
        controller = NikoHomeControlConnection(
            entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    except NetcatError as err:
        raise ConfigEntryNotReady("cannot connect to controller.") from err
    except Exception as err:
        raise ConfigEntryNotReady(
            "unknown error while connecting to controller."
        ) from err

    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
