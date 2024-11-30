"""The Playstation Network integration."""

from __future__ import annotations

from psnawp_api.psn import PlaystationNetwork

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_NPSSO
from .coordinator import PlaystationNetworkCoordinator

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


type PlaystationNetworkConfigEntry = ConfigEntry[PlaystationNetworkCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Set up Playstation Network from a config entry."""

    psn = PlaystationNetwork(entry.data[CONF_NPSSO])
    user = await hass.async_add_executor_job(psn.get_user)

    coordinator = PlaystationNetworkCoordinator(hass, psn, user)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PlaystationNetworkConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
