"""DataUpdateCoordinator for the BLUETTI Modbus integration."""

from dataclasses import dataclass
from typing import NoReturn, override

from bluetti_modbus_lib.base_devices.bluetti_device import BluettiDevice
from modbus_connection.exceptions import (
    AcknowledgeError,
    ModbusError,
    ServerDeviceBusyError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type BluettiModbusConfigEntry = ConfigEntry[BluettiModbusRuntimeData]


class BluettiModbusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Polls a BLUETTI power station over Modbus.

    The device holds its decoded values on itself (``device.values``), so a
    poll here refreshes that state in place rather than returning it - readers
    go straight to ``coordinator.device`` once a refresh has succeeded.
    """

    config_entry: BluettiModbusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BluettiModbusConfigEntry,
        device: BluettiDevice,
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} readings",
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> None:
        """Poll the device, retrying once on a transient device-busy response.

        Codes 5/6 (acknowledge / server device busy) mean the device accepted
        the request but wants more time - retried once immediately rather than
        treated as a hard failure, the same as bluetti-modbus-lib's own
        connection-owning client already does for this hardware.
        """
        try:
            await self.device.async_update()
        except AcknowledgeError, ServerDeviceBusyError:
            LOGGER.debug("%s: device asked for a retry, trying once more", self.name)
            await self._async_read()
        except ModbusError as err:
            self._raise_update_failed(err)

    async def _async_read(self) -> None:
        """Read the device once more, surfacing a failure this time."""
        try:
            await self.device.async_update()
        except ModbusError as err:
            self._raise_update_failed(err)

    def _raise_update_failed(self, err: ModbusError) -> NoReturn:
        """Translate a Modbus failure into UpdateFailed."""
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err


@dataclass(kw_only=True)
class BluettiModbusRuntimeData:
    """Runtime data for a BLUETTI Modbus config entry."""

    coordinator: BluettiModbusDataUpdateCoordinator
    device_info: DeviceInfo
