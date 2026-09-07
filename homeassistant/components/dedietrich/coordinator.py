"""Data update coordinator for De Dietrich devices."""

from datetime import timedelta
import logging
from typing import override

from diematic_modbus import Diematic, DiematicISystem, UpdateReport
from modbus_connection import ModbusConnectionError, ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_MANUFACTURER, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


type DeDietrichConfigEntry = ConfigEntry[DeDietrichDataUpdateCoordinator]


class DeDietrichDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Class to manage fetching De Dietrich data."""

    config_entry: DeDietrichConfigEntry
    device: Diematic | DiematicISystem

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DeDietrichConfigEntry,
        device: Diematic | DiematicISystem,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device
        self._consecutive_failures: dict[str, int] = {}

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        identity = self.device.identity
        # software_version exists only on the iSystem identity, not the base one.
        sw_version = getattr(identity, "software_version", None)
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer=ATTR_MANUFACTURER,
            model=str(identity.boiler_type),
            serial_number=None,
            sw_version=str(sw_version) if sw_version is not None else None,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
            report = await self._retry_failed(report)
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
