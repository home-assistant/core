"""Base class for yale_smart_alarm entity."""

from yalesmartalarmclient import YaleLock

from homeassistant.const import CONF_USERNAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import YaleDataUpdateCoordinator


class YaleEntity(CoordinatorEntity[YaleDataUpdateCoordinator]):
    """Base implementation for Yale device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YaleDataUpdateCoordinator, data: dict) -> None:
        """Initialize an Yale device."""
        super().__init__(coordinator)
        self._attr_unique_id: str = data["address"]
        self._attr_device_info: DeviceInfo = DeviceInfo(
            name=data["name"],
            manufacturer=MANUFACTURER,
            model=MODEL,
            identifiers={(DOMAIN, data["address"])},
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, coordinator.config_entry.data[CONF_USERNAME]),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )


class YaleLockEntity(CoordinatorEntity[YaleDataUpdateCoordinator]):
    """Base implementation for Yale lock device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YaleDataUpdateCoordinator, lock: YaleLock) -> None:
        """Initialize an Yale device."""
        super().__init__(coordinator)
        self._attr_unique_id: str = lock.sid()
        self._attr_device_info = DeviceInfo(
            name=lock.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            identifiers={(DOMAIN, lock.sid())},
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, coordinator.config_entry.data[CONF_USERNAME]),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )
        self.lock_data = lock


class YaleAlarmEntity(CoordinatorEntity[YaleDataUpdateCoordinator], Entity):
    """Base implementation for Yale Alarm device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YaleDataUpdateCoordinator) -> None:
        """Initialize an Yale device."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
