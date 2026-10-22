"""DataUpdateCoordinators that poll a Victron Modbus device."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Self, override

from modbus_connection import ModbusError
from victron_modbus import FAST_SUB_SYSTEMS, SLOW_SUB_SYSTEMS, UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POWER_SCAN_INTERVAL, READINGS_SCAN_INTERVAL
from .models import VictronDevice

_LOGGER = logging.getLogger(__name__)

type VictronModbusConfigEntry = ConfigEntry[VictronModbusData]


class VictronModbusCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Refreshes some of the device's sub-systems on a schedule.

    The shared ``modbus`` integration owns the connection; this coordinator
    only reads. The data is the poll's ``UpdateReport``: a sub-system missing
    from ``updated`` still holds its previous values, so its entities report
    unavailable.
    """

    config_entry: VictronModbusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VictronModbusConfigEntry,
        device: VictronDevice,
        sub_systems: Iterable[str],
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self._sub_systems = tuple(sub_systems)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} {', '.join(self._sub_systems)}",
            config_entry=entry,
            update_interval=update_interval,
        )
        self.device = device
        self._failed: set[str] = set()

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update(self._sub_systems)
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="modbus_error"
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="no_readings"
            ) from ExceptionGroup("every read failed", list(report.failed.values()))
        # The coordinator logs a failed poll once; do the same per sub-system.
        for name in report.failed.keys() - self._failed:
            _LOGGER.warning("Could not read %s: %s", name, report.failed[name])
        for name in self._failed - report.failed.keys():
            _LOGGER.info("Reading %s again", name)
        self._failed = set(report.failed)
        return report


@dataclass
class VictronModbusData:
    """The coordinators of one device: power polled fast, the rest slowly."""

    power: VictronModbusCoordinator
    readings: VictronModbusCoordinator

    @classmethod
    def create(
        cls, hass: HomeAssistant, entry: VictronModbusConfigEntry, device: VictronDevice
    ) -> Self:
        """Build both coordinators for ``device``."""
        return cls(
            power=VictronModbusCoordinator(
                hass, entry, device, FAST_SUB_SYSTEMS, POWER_SCAN_INTERVAL
            ),
            readings=VictronModbusCoordinator(
                hass, entry, device, SLOW_SUB_SYSTEMS, READINGS_SCAN_INTERVAL
            ),
        )

    def coordinator_for(self, sub_system: str) -> VictronModbusCoordinator:
        """The coordinator that polls ``sub_system``."""
        return self.power if sub_system in FAST_SUB_SYSTEMS else self.readings
