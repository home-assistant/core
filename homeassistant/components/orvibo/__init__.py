"""The Orvibo integration."""

from dataclasses import dataclass

from orvibo.s20 import S20, S20Exception

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@dataclass
class OrviboData:
    """State of integration."""

    switch: S20


type OrviboConfigEntry = ConfigEntry[OrviboData]

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: OrviboConfigEntry) -> bool:
    """Set up Orvibo from a config entry."""

    try:
        switch = await hass.async_add_executor_job(
            S20, entry.data[CONF_HOST], entry.data[CONF_MAC]
        )
    except S20Exception:
        raise ConfigEntryNotReady(
            f"Failed to connect to switch at {entry.data[CONF_HOST]}"
        ) from None

    entry.runtime_data = OrviboData(switch=switch)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
