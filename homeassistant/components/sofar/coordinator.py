"""Data update coordinator for Sofar devices."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from modbus_connection import ModbusConnectionError, ModbusError
from propcache.api import cached_property
from sofar_modbus.model import UpdateReport
from sofar_modbus.modern.device import SofarInverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
        assert serial is not None
        identity = self.device.identity
        return dr.DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.device.model or None,
            serial_number=serial,
            hw_version=identity.hardware_version or None,
            sw_version=identity.software_version or None,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
            report = await self._retry_failed(report)
            if not report.updated:
                errors = list(report.failed.values())
                if not errors:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="no_component_answered",
                        translation_placeholders={"name": self.name},
                    )
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_component_answered",
                    translation_placeholders={"name": self.name},
                ) from ExceptionGroup("all components failed to refresh", errors)
        except ModbusError as err:
            # ModbusConnectionError (dead link) and ModbusTimeoutError reach
            # here; per-block failures once alive land in report.failed instead.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
                translation_placeholders={"error": str(err)},
            ) from err
        else:
            return report

    async def _retry_failed(self, report: UpdateReport) -> UpdateReport:
        """Retry failures once; skip if none answered, to avoid doubling timeout."""
        if report.failed and report.updated:
            updated: set[str] = set()
            failed: dict[str, ModbusError] = {}
            for name in report.failed:
                try:
                    await getattr(self.device, name).async_update()
                except ModbusConnectionError:
                    raise
                except ModbusError as err:
                    failed[name] = err
                else:
                    updated.add(name)
            report = UpdateReport(report.updated | updated, failed)

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

        return report


@dataclass
class SofarRuntimeData:
    """Class to hold runtime data."""

    readings: SofarDataUpdateCoordinator
    settings: SofarDataUpdateCoordinator
    inverter_device_id: str

    @property
    def served_components(self) -> frozenset[str]:
        """Component names this inverter polls, answered or not."""
        device = self.readings.device
        return frozenset(device.readings_components) | frozenset(
            device.settings_components
        )

    def coordinator_for(self, component: str) -> SofarDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        if component in self.readings.device.readings_components:
            return self.readings
        return self.settings


type SofarConfigEntry = ConfigEntry[SofarRuntimeData]
