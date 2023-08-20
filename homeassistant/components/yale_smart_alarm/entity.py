"""Base class for yale_smart_alarm entity."""

from homeassistant.const import CONF_NAME, CONF_USERNAME
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import YaleDataUpdateCoordinator


class YaleEntity(CoordinatorEntity[YaleDataUpdateCoordinator], Entity):
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
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_USERNAME]),
        )


class YaleAlarmEntity(CoordinatorEntity[YaleDataUpdateCoordinator], Entity):
    """Base implementation for Yale Alarm device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YaleDataUpdateCoordinator) -> None:
        """Initialize an Yale device."""
        super().__init__(coordinator)
        panel_info = coordinator.data["panel_info"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.data[CONF_USERNAME])},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=coordinator.entry.data[CONF_NAME],
            connections={(CONNECTION_NETWORK_MAC, panel_info["mac"])},
            sw_version=panel_info["version"],
        )
