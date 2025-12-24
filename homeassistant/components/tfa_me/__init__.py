"""TFA.me station integration: ___init___.py."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_NAME_WITH_STATION_ID, DOMAIN, LOCAL_POLL_INTERVAL
from .coordinator import TFAmeConfigEntry, TFAmeDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TFAmeConfigEntry) -> bool:
    """Set up a TFA.me station."""
    # Get IP or station-ID
    host = entry.data[CONF_IP_ADDRESS]
    # Use default poll interval
    delta_interval = timedelta(seconds=LOCAL_POLL_INTERVAL)

    # Use name with station ID option
    name_with_station_id = entry.data[CONF_NAME_WITH_STATION_ID]

    # First request for sensor data
    entry.runtime_data = coordinator = TFAmeDataCoordinator(
        hass, entry, host, delta_interval, name_with_station_id
    )
    await coordinator.async_config_entry_first_refresh()

    # Save coordinator for later usage
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    assert entry.unique_id

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
