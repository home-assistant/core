"""Base entity for Coolmaster integration."""
from typing import Any

from pycoolmasternet_async.coolmasternet import CoolMasterNetUnit

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CoolmasterDataUpdateCoordinator
from .const import DATA_COORDINATOR, DATA_INFO, DOMAIN


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


def async_add_entities_for_platform(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    cls: type[CoolmasterEntity],
    **kwargs: Any,
) -> None:
    """Add CoolMasterNet platform entities."""
    info = hass.data[DOMAIN][config_entry.entry_id][DATA_INFO]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [cls(coordinator, unit_id, info, **kwargs) for unit_id in coordinator.data]
    )
