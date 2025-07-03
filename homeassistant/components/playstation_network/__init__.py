"""The PlayStation Network integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_NPSSO
from .coordinator import PlaystationNetworkConfigEntry, PlaystationNetworkCoordinator
from .helpers import PlaystationNetwork

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Set up Playstation Network from a config entry."""

    psn = PlaystationNetwork(hass, entry.data[CONF_NPSSO])

    coordinator = PlaystationNetworkCoordinator(hass, psn, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
