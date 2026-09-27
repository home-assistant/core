"""The ScorpionTrack integration."""

from pyscorpiontrack import ScorpionTrackClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARE_TOKEN, PLATFORMS
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
