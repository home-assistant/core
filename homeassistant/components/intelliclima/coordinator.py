"""DataUpdateCoordinator for IntelliClima."""

from dataclasses import dataclass
from typing import override

from pyintelliclima import IntelliClimaAPI, IntelliClimaAPIError, IntelliClimaDevices
from pyintelliclima.intelliclima_types import IntelliClimaFilterStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, FILTER_SCAN_INTERVAL, LOGGER

type IntelliClimaConfigEntry = ConfigEntry[IntelliClimaData]


class IntelliClimaCoordinator(DataUpdateCoordinator[IntelliClimaDevices]):
    """Coordinator to manage fetching IntelliClima data."""

    def __init__(
        self, hass: HomeAssistant, entry: IntelliClimaConfigEntry, api: IntelliClimaAPI
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.api = api

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator - called once during first refresh."""
        # Authenticate and get initial device list
        try:
            await self.api.authenticate()
        except IntelliClimaAPIError as err:
            raise UpdateFailed(f"Failed to set up IntelliClima: {err}") from err

    @override
    async def _async_update_data(self) -> IntelliClimaDevices:
        """Fetch data from API."""
        try:
            # Poll status for all devices
            return await self.api.get_all_device_status()

        except IntelliClimaAPIError as err:
            raise UpdateFailed(f"Failed to update data: {err}") from err


class IntelliClimaFilterCoordinator(
    DataUpdateCoordinator[dict[str, IntelliClimaFilterStatus]]
):
    """Coordinator to manage fetching IntelliClima filter status, polled once a day."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntelliClimaConfigEntry,
        api: IntelliClimaAPI,
        device_serials: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_filter",
            update_interval=FILTER_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.api = api
        self._device_serials = device_serials

    @override
    async def _async_update_data(self) -> dict[str, IntelliClimaFilterStatus]:
        """Fetch filter status for all devices."""
        try:
            return {
                serial: await self.api.get_filter_status(serial)
                for serial in self._device_serials
            }
        except IntelliClimaAPIError as err:
            raise UpdateFailed(f"Failed to update filter status: {err}") from err


@dataclass
class IntelliClimaData:
    """Runtime data for the IntelliClima config entry."""

    devices_coordinator: IntelliClimaCoordinator
    filter_coordinator: IntelliClimaFilterCoordinator
