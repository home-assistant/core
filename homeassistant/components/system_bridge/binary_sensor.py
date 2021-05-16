"""Support for System Bridge binary sensors."""
from __future__ import annotations

from systembridge import Bridge

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import BridgeDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up System Bridge binary sensor based on a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    bridge: Bridge = coordinator.data

    if bridge.battery.hasBattery:
        async_add_entities([BridgeBatteryIsChargingBinarySensor(coordinator, bridge)])


class BridgeBinarySensor(BridgeDeviceEntity, BinarySensorEntity):
    """Defines a System Bridge binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bridge: Bridge,
        key: str,
        name: str,
        icon: str | None,
        device_class: str | None,
        enabled_by_default: bool,
    ) -> None:
        """Initialize System Bridge binary sensor."""
        self._device_class = device_class

        super().__init__(coordinator, bridge, key, name, icon, enabled_by_default)

    @property
    def device_class(self) -> str | None:
        """Return the class of this binary sensor."""
        return self._device_class


class BridgeBatteryIsChargingBinarySensor(BridgeBinarySensor):
    """Defines a Battery is charging binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, bridge: Bridge):
        """Initialize System Bridge binary sensor."""
        super().__init__(
            coordinator,
            bridge,
            "battery_is_charging",
            "Battery Is Charging",
            None,
            DEVICE_CLASS_BATTERY_CHARGING,
            True,
        )

    @property
    def is_on(self) -> bool:
        """Return if the state is on."""
        bridge: Bridge = self.coordinator.data
        return bridge.battery.isCharging
