"""Data update coordinator for WAFE heat recovery units."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from wafe_modbus import WafeUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

# A poll is one request of a few milliseconds on the local network, and the unit
# state should follow a change made in the vendor app quickly.
SCAN_INTERVAL = timedelta(seconds=5)

type WafeConfigEntry = ConfigEntry[WafeDataUpdateCoordinator]


class WafeDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Poll the live values of a WAFE unit."""

    config_entry: WafeConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: WafeConfigEntry, device: WafeUnit
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the unit to the device registry."""
        if TYPE_CHECKING:
            assert self.config_entry.unique_id is not None
        model = self.device.model
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=model.name if model is not None else None,
            name=self.config_entry.title,
        )

    @override
    async def _async_update_data(self) -> None:
        try:
            await self.device.async_ensure_setup()
            await self.device.status.async_update()
        except (ModbusConnectionError, ModbusTimeoutError) as err:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN,
                translation_key="unit_unreachable",
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
