"""DataUpdateCoordinator for the BLUETTI Modbus integration."""

from dataclasses import dataclass
from typing import override

from bluetti_modbus_lib import Balco260
from modbus_connection import ModbusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type BluettiModbusConfigEntry = ConfigEntry[BluettiModbusRuntimeData]


class BluettiModbusDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Polls a BLUETTI power station; its values are read from ``device.values``."""

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
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} readings",
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> None:
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

        # An address can be reassigned to a different physical unit after setup.
        serial = str(self.device.values["d_serial"])
        issue_id = f"wrong_device_{self.config_entry.entry_id}"
        if serial != self.config_entry.unique_id:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="wrong_device",
                translation_placeholders={
                    "host": self.config_entry.data[CONF_HOST],
                    "expected": str(self.config_entry.unique_id),
                    "found": serial,
                },
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_device",
            )
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)


@dataclass(kw_only=True)
class BluettiModbusRuntimeData:
    """Runtime data for a BLUETTI Modbus config entry."""

    coordinator: BluettiModbusDataUpdateCoordinator
    device_info: DeviceInfo
