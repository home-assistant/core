"""The Google Wifi integration coordinator."""

from datetime import timedelta
from typing import override

from googlewifiapi import GoogleWifiAPI, GoogleWifiStatus
from googlewifiapi.exception import GoogleWifiClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type GoogleWifiConfigEntry = ConfigEntry[GoogleWifiCoordinator]


class GoogleWifiCoordinator(DataUpdateCoordinator[GoogleWifiStatus]):
    """Coordinates entities for one Google Wifi device."""

    config_entry: GoogleWifiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GoogleWifiConfigEntry,
        api: GoogleWifiAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api = api
        self.hardware_id = entry.unique_id or entry.entry_id

    @callback
    def _async_update_sw_version(self, status: GoogleWifiStatus) -> None:
        """Update the device registry when the firmware version changed."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, self.hardware_id), self.config_entry.entry_id
        )
        sw_version = status.software.software_version
        if device is not None and device.sw_version != sw_version:
            device_registry.async_update_device(device.id, sw_version=sw_version)

    @override
    async def _async_update_data(self) -> GoogleWifiStatus:
        """Fetch data from the API."""
        try:
            status = await self.api.async_update()
        except GoogleWifiClientError as err:
            raise UpdateFailed("Unable to fetch Google Wifi status") from err
        self._async_update_sw_version(status)
        return status
