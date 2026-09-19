"""The mawaqit_prayer_times component."""

from mawaqit import AsyncMawaqitClient

from homeassistant.const import CONF_API_KEY, CONF_UUID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import PrayerTimeCoordinator
from .types import MawaqitConfigEntry, MawaqitData

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MawaqitConfigEntry
) -> bool:
    """Set up the Mawaqit Prayer Component."""
    client = AsyncMawaqitClient(
        mosque=config_entry.data[CONF_UUID],
        token=config_entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    prayer_time_coordinator = PrayerTimeCoordinator(hass, config_entry, client)
    await prayer_time_coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = MawaqitData(
        prayer_time_coordinator=prayer_time_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MawaqitConfigEntry
) -> bool:
    """Unload Mawaqit Prayer entry from config_entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
