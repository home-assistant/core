"""Data update coordinator for De Dietrich devices."""

from datetime import timedelta
import logging
from typing import override

from diematic_modbus import Diematic, DiematicISystem, UpdateReport
from modbus_connection import ModbusError
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

    @override
    async def _async_setup(self) -> None:
        """Read the identity before registering device information."""
        try:
            await self.device.identity.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        identity = self.device.identity
        # software_version exists only on the iSystem identity, not the base one.
        sw_version = getattr(identity, "software_version", None)
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer=ATTR_MANUFACTURER,
            serial_number=None,
            sw_version=str(sw_version) if sw_version is not None else None,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        # Failed blocks keep their previous values in the library and are
        # retried on the next poll, so only a total failure aborts the update.
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
        return report
