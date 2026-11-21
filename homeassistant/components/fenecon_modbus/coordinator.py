"""Data update coordinator for the Fenecon Modbus integration."""

from typing import override

from fenecon_modbus import (
    FeneconData,
    FeneconDeviceInfo,
    FeneconError,
    FeneconModbusClient,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type FeneconConfigEntry = ConfigEntry[FeneconCoordinator]


class FeneconCoordinator(DataUpdateCoordinator[FeneconData]):
    """Poll the FEMS via Modbus/TCP."""

    config_entry: FeneconConfigEntry
    device_info: FeneconDeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FeneconConfigEntry,
        client: FeneconModbusClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=f"Fenecon {client.host}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_setup(self) -> None:
        """Read the static identification data once."""
        try:
            self.device_info = await self.client.read_device_info()
        except FeneconError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

    @override
    async def _async_update_data(self) -> FeneconData:
        """Read all data points."""
        try:
            return await self.client.read_data()
        except FeneconError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err
