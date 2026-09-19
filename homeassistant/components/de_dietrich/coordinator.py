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


CHILD_COMPONENT_DEVICE_NAMES: dict[str, str] = {
    "circuit_a": "Heating circuit A",
    "circuit_b": "Heating circuit B",
    "circuit_c": "Heating circuit C",
}


class DeDietrichDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Class to manage fetching De Dietrich data."""

    config_entry: DeDietrichConfigEntry
    device: Diematic | DiematicISystem
    parent_device_id: str

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
        self.parent_device_id = ""

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
        """Return main boiler device information."""
        device = self.device
        sw_version = (
            device.identity.software_version
            if isinstance(device, DiematicISystem)
            else None
        )
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer=ATTR_MANUFACTURER,
            sw_version=str(sw_version) if sw_version is not None else None,
        )

    def child_device_info(self, component: str) -> dr.ChildDeviceInfo | None:
        """Return child device information when the component is present."""
        if component not in CHILD_COMPONENT_DEVICE_NAMES:
            return None
        if component == "circuit_a":
            if not self.device.circuit_a_present:
                return None
        elif component == "circuit_b":
            if not self.device.circuit_b_present:
                return None
        elif component == "circuit_c":
            if not (
                isinstance(self.device, DiematicISystem)
                and self.device.circuit_c_present
            ):
                return None
        return dr.ChildDeviceInfo(
            identifiers={(DOMAIN, f"{self.config_entry.entry_id}_{component}")},
            parent_device_id=self.parent_device_id,
            name=CHILD_COMPONENT_DEVICE_NAMES[component],
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
