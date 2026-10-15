"""Data update coordinator for Sofar devices."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import override

from modbus_connection import ModbusError
from propcache.api import cached_property
from sofar_modbus.model import UpdateReport
from sofar_modbus.modern.device import SofarInverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_MANUFACTURER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SofarDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Class to manage fetching Sofar data."""

    config_entry: SofarConfigEntry
    device: SofarInverter

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SofarConfigEntry,
        device: SofarInverter,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll
        self._consecutive_failures: dict[str, int] = {}

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        serial = self.device.serial_number
        identity = self.device.identity
        info = dr.DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.device.model or None,
            serial_number=serial,
        )
        if identity.hardware_version:
            info.hw_version = identity.hardware_version
        if identity.software_version:
            info.sw_version = identity.software_version
        return info

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        self._log_component_changes(report)
        if self.device.unrecognized:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unrecognized_inverter_model",
            )
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )
        return report

    def _log_component_changes(self, report: UpdateReport) -> None:
        """Log a component's first failure and its recovery, once each."""
        for name, cause in report.failed.items():
            prev = self._consecutive_failures.get(name, 0)
            self._consecutive_failures[name] = prev + 1
            if prev == 0:
                _LOGGER.warning(
                    "%s: %s failed to refresh and is keeping its previous values: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in report.updated:
            if self._consecutive_failures.pop(name, None) is not None:
                _LOGGER.info("%s: %s is available again", self.name, name)


@dataclass
class SofarRuntimeData:
    """Class to hold runtime data."""

    readings: SofarDataUpdateCoordinator
    settings: SofarDataUpdateCoordinator
    inverter_device_id: str
    wired_packs: set[int] = field(default_factory=set)

    @property
    def served_components(self) -> frozenset[str]:
        """Component names this inverter polls, answered or not."""
        return self.readings.device.expected_components

    def coordinator_for(self, component: str) -> SofarDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        if component in self.readings.device.expected_readings_components:
            return self.readings
        return self.settings


type SofarConfigEntry = ConfigEntry[SofarRuntimeData]
