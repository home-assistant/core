"""The ScorpionTrack integration."""

from pyscorpiontrack import ScorpionTrackClient

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARE_TOKEN, DOMAIN, PLATFORMS
from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ScorpionTrackConfigEntry
) -> bool:
    """Set up ScorpionTrack from a config entry."""
    client = ScorpionTrackClient(
        session=async_get_clientsession(hass),
        token=entry.data[CONF_SHARE_TOKEN],
    )
    coordinator = ScorpionTrackCoordinator(hass, client, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ScorpionTrackConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ScorpionTrackConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow manual removal of vehicles no longer included in the share."""
    if entry.state is not ConfigEntryState.LOADED:
        return False

    coordinator = entry.runtime_data
    return coordinator.last_update_success and not any(
        (DOMAIN, f"{coordinator.data.id}_{vehicle_id}") in device_entry.identifiers
        for vehicle_id in coordinator.vehicles_by_id
    )
