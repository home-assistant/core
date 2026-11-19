"""DataUpdateCoordinator for the BLUETTI Modbus integration."""

from dataclasses import dataclass
import logging
from typing import Any, override

from bluetti_modbus_lib import Balco260
from modbus_connection import ModbusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BluettiModbusConfigEntry = ConfigEntry[BluettiModbusRuntimeData]


class BluettiModbusDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls a BLUETTI power station for its decoded field values."""

    config_entry: BluettiModbusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BluettiModbusConfigEntry,
        device: Balco260,
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} readings",
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Poll the device."""
        # Besides BluettiModbusConnectionError, the library lets a device still
        # busy after its retry, or a failed teardown of the link, through unwrapped.
        try:
            await self.device.async_update_with_retry()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        values = self.device.values
        # An address can be reassigned to a different physical unit after setup.
        serial = str(values["d_serial"])
        if serial != self.config_entry.unique_id:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_device",
            )
        return values


@dataclass(kw_only=True)
class BluettiModbusRuntimeData:
    """Runtime data for a BLUETTI Modbus config entry."""

    coordinator: BluettiModbusDataUpdateCoordinator
    device_info: DeviceInfo
    serial: str
