"""Base entity for Coolmaster integration."""
from pycoolmasternet_async.coolmasternet import CoolMasterNetUnit

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CoolmasterDataUpdateCoordinator
from .const import DOMAIN


class CoolmasterEntity(CoordinatorEntity[CoolmasterDataUpdateCoordinator]):
    """Representation of a Coolmaster entity."""

    def __init__(
        self,
        coordinator: CoolmasterDataUpdateCoordinator,
        unit_id: str,
        info: dict[str, str],
    ) -> None:
        """Initiate CoolmasterEntity."""
        super().__init__(coordinator)
        self._unit_id: str = unit_id
        self._unit: CoolMasterNetUnit = coordinator.data[self._unit_id]
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, unit_id)},
            manufacturer="CoolAutomation",
            model="CoolMasterNet",
            name=unit_id,
            sw_version=info["version"],
        )
        if hasattr(self, "entity_description"):
            self._attr_unique_id: str = f"{unit_id}-{self.entity_description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        self._unit = self.coordinator.data[self._unit_id]
        super()._handle_coordinator_update()
