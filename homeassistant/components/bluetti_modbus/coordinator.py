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
        pack_summary: Balco260,
        packs: dict[int, Balco260],
    ) -> None:
        """Initialize the coordinator."""
        self._device = device
        self._pack_summary = pack_summary
        self._packs = packs
        # Each expansion pack's values, by unit ID, for the packs that answered
        # the last poll.
        self.pack_values: dict[int, dict[str, Any]] = {}
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
            await self._device.async_update_with_retry()
            await self._pack_summary.async_update_with_retry()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        values = self._device.values
        # An address can be reassigned to a different physical unit after setup.
        serial = str(values["d_serial"])
        if serial != self.config_entry.unique_id:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_device",
            )
        summary = self._pack_summary.values
        await self._async_update_packs(summary["d_num_battery_packs"])
        return values | summary

    async def _async_update_packs(self, count: int) -> None:
        """Read the expansion packs the pack summary counts.

        The count includes the built-in pack. A pack that fails to answer
        only leaves its own entities unavailable.
        """
        pack_values: dict[int, dict[str, Any]] = {}
        # Unit IDs in order, so the first count - 1 are the packs counted.
        for unit_id, pack in list(self._packs.items())[: max(count - 1, 0)]:
            try:
                await pack.async_update_with_retry()
            except ModbusError as err:
                _LOGGER.debug(
                    "Battery pack at unit %s did not answer: %s", unit_id, err
                )
                continue
            pack_values[unit_id] = pack.values
        self.pack_values = pack_values


@dataclass(kw_only=True)
class BluettiModbusRuntimeData:
    """Runtime data for a BLUETTI Modbus config entry."""

    coordinator: BluettiModbusDataUpdateCoordinator
    device_info: DeviceInfo
    # The power station's device, which expansion packs are attached to.
    device_id: str
    serial: str
