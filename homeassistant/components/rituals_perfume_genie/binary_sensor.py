"""Support for Rituals Perfume Genie binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity

CHARGING_SUFFIX = " Battery Charging"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser binary sensors."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        DiffuserBatteryChargingBinarySensor(coordinator)
        for coordinator in coordinators.values()
        if coordinator.diffuser.has_battery
    )


class DiffuserBatteryChargingBinarySensor(DiffuserEntity, BinarySensorEntity):
    """Representation of a diffuser battery charging binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: RitualsDataUpdateCoordinator) -> None:
        """Initialize the battery charging binary sensor."""
        super().__init__(coordinator, CHARGING_SUFFIX)
        self._attr_unique_id = f"{coordinator.diffuser.hublot}-charging"

    @property
    def is_on(self) -> bool:
        """Return the state of the battery charging binary sensor."""
        return self.coordinator.diffuser.charging
