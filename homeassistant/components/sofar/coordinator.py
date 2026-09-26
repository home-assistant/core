"""Data update coordinator for Sofar devices."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import override

from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from propcache.api import cached_property
from sofar_modbus.model import UpdateReport
from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.tuning import LinkTuner, TimedUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_MANUFACTURER, BATTERY_COMPONENTS, DOMAIN

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
        tuner: LinkTuner,
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
        self._tuner = tuner
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
            report = await self._async_observed_poll()
            if not report.updated:
                errors = list(report.failed.values())
                if not errors:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="no_component_answered",
                    )
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_component_answered",
                ) from ExceptionGroup("all components failed to refresh", errors)
        except ModbusError as err:
            # ModbusConnectionError (dead link) and ModbusTimeoutError reach
            # here; per-block failures once alive land in report.failed instead.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        else:
            return report

    async def _async_observed_poll(self) -> UpdateReport:
        """Poll once; a timeout either attempt hit must reach the tuner."""
        attempted: dict[str, ModbusError] = {}
        try:
            report = await self._poll()
            attempted = dict(report.failed)
            report = await self._retry_failed(report)
        except ModbusError as err:
            self._tuner.observe_failure(_timed_out(attempted) or err)
            raise
        self._tuner.observe(
            UpdateReport(report.updated, _both_attempts(attempted, report.failed))
        )
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


def _timed_out(failures: Mapping[str, ModbusError]) -> ModbusTimeoutError | None:
    """Whichever of these failures timed out, if any of them did."""
    return next(
        (err for err in failures.values() if isinstance(err, ModbusTimeoutError)), None
    )


def _both_attempts(
    attempted: Mapping[str, ModbusError], retried: Mapping[str, ModbusError]
) -> dict[str, ModbusError]:
    """Both attempts' failures, a timeout outranking any other error."""
    failures = dict(attempted)
    for name, err in retried.items():
        if not isinstance(failures.get(name), ModbusTimeoutError):
            failures[name] = err
    return failures


@dataclass
class SofarRuntimeData:
    """Class to hold runtime data."""

    readings: SofarDataUpdateCoordinator
    settings: SofarDataUpdateCoordinator
    inverter_device_id: str
    link: TimedUnit
    tuner: LinkTuner
    wired_packs: set[int] = field(default_factory=set)

    @property
    def served_components(self) -> frozenset[str]:
        """Component names this inverter polls, answered or not."""
        device = self.readings.device
        return frozenset(device.readings_components) | frozenset(
            device.settings_components
        )

    def pack_is_wired(self, number: int) -> bool:
        """Whether a pack has answered, so it physically exists."""
        component_name = BATTERY_COMPONENTS[number]
        if component_name not in self.served_components:
            return False
        component = getattr(self.readings.device, component_name)
        return bool(getattr(component, f"battery_voltage_{number}", None))

    def coordinator_for(self, component: str) -> SofarDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        if component in self.readings.device.readings_components:
            return self.readings
        return self.settings


type SofarConfigEntry = ConfigEntry[SofarRuntimeData]
