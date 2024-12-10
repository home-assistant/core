"""The ohme integration."""

from dataclasses import dataclass
import logging

from ohme import OhmeApiClient

from homeassistant import core
from homeassistant.config_entries import ConfigEntry

from .const import PLATFORMS
from .coordinator import OhmeCoordinator

_LOGGER = logging.getLogger(__name__)

type OhmeConfigEntry = ConfigEntry[OhmeRuntimeData]


@dataclass
class OhmeRuntimeData:
    """Store volatile data."""

    client: OhmeApiClient
    coordinator: OhmeCoordinator


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ohme from a config entry."""

    client = OhmeApiClient(entry.data["email"], entry.data["password"])
    await client.async_create_session()
    await client.async_update_device_info()

    coordinator = OhmeCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = OhmeRuntimeData(client, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
