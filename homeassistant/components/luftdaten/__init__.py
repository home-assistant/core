"""Support for Sensor.Community stations.

Sensor.Community was previously called Luftdaten, hence the domain differs from
the integration name.
"""

from luftdaten import Luftdaten

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_SENSOR_ID
from .coordinator import LuftdatenConfigEntry, LuftdatenDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LuftdatenConfigEntry) -> None:
    """Set up Sensor.Community as config entry."""

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=str(entry.data[CONF_SENSOR_ID])
        )

    sensor_community = Luftdaten(
        entry.data[CONF_SENSOR_ID], httpx_client=get_async_client(hass)
    )

    coordinator = LuftdatenDataUpdateCoordinator(hass, entry, sensor_community)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LuftdatenConfigEntry) -> None:
    """Unload an Sensor.Community config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
