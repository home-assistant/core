"""The VelaSmart integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from velasmart import VelaSmartApiClient, VelaSmartApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


@dataclass
class VelasmartData:
    """Runtime data for the VelaSmart integration."""

    client: VelaSmartApiClient
    coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]]


type VelasmartConfigEntry = ConfigEntry[VelasmartData]


async def async_setup_entry(hass: HomeAssistant, entry: VelasmartConfigEntry) -> bool:
    """Set up VelaSmart from a config entry."""
    client = VelaSmartApiClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    async def async_update_data() -> dict[str, dict[str, Any]]:
        """Fetch device state from the cloud API."""
        try:
            devices = await client.get_devices()
        except VelaSmartApiError as err:
            raise UpdateFailed(str(err)) from err
        return {device["id"]: device for device in devices}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = VelasmartData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VelasmartConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: VelasmartConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow removal of any device."""
    return True
