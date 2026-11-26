"""Data update coordinator for the Fenecon Modbus integration."""

from collections.abc import Awaitable, Callable
from typing import override

from fenecon_modbus import (
    FeneconConnectionError,
    FeneconData,
    FeneconDeviceInfo,
    FeneconInvalidResponseError,
    FeneconModbusClient,
    FeneconTimeoutError,
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

    async def _read[T](self, read: Callable[[], Awaitable[T]]) -> T:
        """Read from the FEMS and map library errors to translated errors."""
        try:
            return await read()
        except FeneconTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout",
                translation_placeholders={"host": self.client.host},
            ) from err
        except FeneconConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.client.host},
            ) from err
        except FeneconInvalidResponseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from err

    @override
    async def _async_setup(self) -> None:
        """Read the static identification data once."""
        self.device_info = await self._read(self.client.read_device_info)

    @override
    async def _async_update_data(self) -> FeneconData:
        """Read all data points."""
        return await self._read(self.client.read_data)
