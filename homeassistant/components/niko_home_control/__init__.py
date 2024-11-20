"""The Niko home control integration."""

from __future__ import annotations

from dataclasses import dataclass

from nikohomecontrol import NikoHomeControlConnection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS: list[Platform] = [Platform.LIGHT]

type NikoHomeControlConfigEntry = ConfigEntry[NikoHomeControlRuntimeData]


@dataclass
class NikoHomeControlRuntimeData:
    """Niko Home Control runtime data."""

    controller: NikoHomeControlConnection


async def async_setup_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Set Niko Home Control from a config entry."""
    controller = NikoHomeControlConnection(entry.data[CONF_HOST], entry.data[CONF_PORT])

    if not controller:
        raise ConfigEntryNotReady(
            "cannot connect to controller, please check the host & port are correct."
        )

    entry.runtime_data = NikoHomeControlRuntimeData(controller)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NikoHomeControlConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
