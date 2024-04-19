"""Entity classes for the Lektrico integration."""

from __future__ import annotations

from lektricowifi import InfoForCharger

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LektricoDeviceDataUpdateCoordinator
from .const import DOMAIN


class LektricoEntity(CoordinatorEntity[LektricoDeviceDataUpdateCoordinator]):
    """Define an Lektrico entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        friendly_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        _infoForCharger: InfoForCharger = coordinator.data

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            model=f"{coordinator.device_type.upper()} {coordinator.serial_number} rev.{coordinator.board_revision}",
            name=friendly_name,
            manufacturer="Lektrico",
            sw_version=_infoForCharger.fw_version,
        )
