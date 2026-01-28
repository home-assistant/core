"""DataUpdateCoordinator for IntelliClima."""

from pyintelliclima import IntelliClimaAPI, IntelliClimaAPIError, IntelliClimaDevices

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type IntelliClimaConfigEntry = ConfigEntry[IntelliClimaCoordinator]


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

    async def _async_setup(self) -> None:
        """Set up the coordinator - called once during first refresh."""
        # Authenticate and get initial device list
        try:
            await self.api.authenticate()
        except IntelliClimaAPIError as err:
            raise UpdateFailed(f"Failed to set up IntelliClima: {err}") from err

    async def _async_update_data(self) -> IntelliClimaDevices:
        """Fetch data from API."""
        try:
            # Poll status for all devices
            return await self.api.get_all_device_status()

        except IntelliClimaAPIError as err:
            raise UpdateFailed(f"Failed to update data: {err}") from err
