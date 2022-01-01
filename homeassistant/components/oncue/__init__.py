"""The Oncue integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiooncue import LoginFailedException, Oncue

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONNECTION_EXCEPTIONS, DOMAIN

PLATFORMS: list[str] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oncue from a config entry."""
    data = entry.data
    client = Oncue(
        data[CONF_USERNAME], data[CONF_PASSWORD], async_get_clientsession(hass)
    )
    try:
        await client.async_login()
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady(ex) from ex
    except LoginFailedException as ex:
        _LOGGER.error("Failed to login to oncue service: %s", ex)
        return False

    coordinator = OnCueDataUpdateCoordinator(hass, client, entry)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class OnCueDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific TPLink device."""

    def __init__(
        self,
        hass: HomeAssistant,
        oncue: Oncue,
        entry: ConfigEntry,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data."""
        self.entry = entry
        self.oncue = oncue
        super().__init__(
            hass,
            _LOGGER,
            name=f"Oncue {entry.data[CONF_USERNAME]}",
            update_interval=timedelta(minutes=10),
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        devices = await self.oncue.async_list_devices_with_params()
        indexed_devices = {}
        for device in devices:
            indexed_devices[device["id"]] = {
                "name": device["displayname"],
                "state": device[
                    "devicestate",
                ],
                "product_name": device["productname"],
                "version": device["version"],
                "serial_number": device["serialnumber"],
                "sensors": {
                    param_dict["name"]: param_dict
                    for param_dict in device["parameters"]
                },
            }
        self.data = indexed_devices
