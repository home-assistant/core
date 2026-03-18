"""Binary sensor platform for Zinvolt integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ZinvoltConfigEntry, ZinvoltData, ZinvoltDeviceCoordinator
from .entity import ZinvoltEntity

POINT_ENTITIES = {
    "communication": BinarySensorDeviceClass.PROBLEM,
    "voltage": BinarySensorDeviceClass.PROBLEM,
    "current": BinarySensorDeviceClass.PROBLEM,
    "temperature": BinarySensorDeviceClass.HEAT,
    "charge": BinarySensorDeviceClass.PROBLEM,
    "discharge": BinarySensorDeviceClass.PROBLEM,
    "other": BinarySensorDeviceClass.PROBLEM,
}


@dataclass(kw_only=True, frozen=True)
class ZinvoltBatteryStateDescription(BinarySensorEntityDescription):
    """Binary sensor description for Zinvolt battery state."""

    is_on_fn: Callable[[ZinvoltData], bool]


SENSORS: tuple[ZinvoltBatteryStateDescription, ...] = (
    ZinvoltBatteryStateDescription(
        key="on_grid",
        translation_key="on_grid",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda state: state.battery.current_power.on_grid,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZinvoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    entities: list[BinarySensorEntity] = [
        ZinvoltBatteryStateBinarySensor(coordinator, description)
        for description in SENSORS
        for coordinator in entry.runtime_data.values()
    ]
    entities.extend(
        ZinvoltPointBinarySensor(coordinator, point)
        for coordinator in entry.runtime_data.values()
        for point in coordinator.data.points
        if point in POINT_ENTITIES
    )
    async_add_entities(entities)


class ZinvoltBatteryStateBinarySensor(ZinvoltEntity, BinarySensorEntity):
    """Zinvolt battery state binary sensor."""

    entity_description: ZinvoltBatteryStateDescription

    def __init__(
        self,
        coordinator: ZinvoltDeviceCoordinator,
        description: ZinvoltBatteryStateDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.battery.serial_number}.{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)


class ZinvoltPointBinarySensor(ZinvoltEntity, BinarySensorEntity):
    """Zinvolt battery state binary sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ZinvoltDeviceCoordinator, point: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.point = point
        self._attr_translation_key = point
        self._attr_device_class = POINT_ENTITIES[point]
        self._attr_unique_id = f"{coordinator.data.battery.serial_number}.{point}"

    @property
    def available(self) -> bool:
        """Return the availability of the binary sensor."""
        return super().available and self.point in self.coordinator.data.points

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return not self.coordinator.data.points[self.point]
