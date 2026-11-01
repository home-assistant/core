"""Data update coordinator for E3/DC devices."""

from datetime import timedelta
import logging
from typing import override

from e3dc_ess_modbus import E3dcPowerStation, NotAnE3dcError, UpdateReport
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type E3dcConfigEntry = ConfigEntry[E3dcDataUpdateCoordinator]


class E3dcDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll what the power station measures."""

    config_entry: E3dcConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: E3dcConfigEntry,
        device: E3dcPowerStation,
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
        self._failing: set[str] = set()

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        identity = self.device.identity
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.unique_id or "")},
            manufacturer=identity.manufacturer or DEFAULT_NAME,
            model=identity.model or None,
            serial_number=identity.serial_number or None,
            sw_version=identity.firmware_release or None,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update_readings()
        except NotAnE3dcError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="not_e3dc",
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if report.failed and not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )

        for name, cause in report.failed.items():
            if name not in self._failing:
                _LOGGER.info(
                    "%s: %s failed to refresh and is unavailable: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in self._failing & report.updated:
            _LOGGER.info("%s: %s is available again", self.name, name)
        self._failing = (self._failing - report.updated) | set(report.failed)
        return report
