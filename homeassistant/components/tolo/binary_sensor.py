"""TOLO Sauna binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ToloConfigEntry, ToloSaunaUpdateCoordinator
from .entity import ToloSaunaCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for TOLO Sauna."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ToloFlowInBinarySensor(coordinator, entry),
            ToloFlowOutBinarySensor(coordinator, entry),
        ]
    )


class ToloFlowInBinarySensor(ToloSaunaCoordinatorEntity, BinarySensorEntity):
    """Water In Valve Sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "water_in_valve"
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ToloConfigEntry
    ) -> None:
        """Initialize TOLO Water In Valve entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_flow_in"

    @property
    def is_on(self) -> bool:
        """Return if flow in valve is open."""
        return self.coordinator.data.status.flow_in


class ToloFlowOutBinarySensor(ToloSaunaCoordinatorEntity, BinarySensorEntity):
    """Water Out Valve Sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "water_out_valve"
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ToloConfigEntry
    ) -> None:
        """Initialize TOLO Water Out Valve entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_flow_out"

    @property
    def is_on(self) -> bool:
        """Return if flow out valve is open."""
        return self.coordinator.data.status.flow_out
