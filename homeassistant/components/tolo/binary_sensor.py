"""TOLO Sauna binary sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ToloFlowInBinarySensor(coordinator, entry),
            ToloFlowOutBinarySensor(coordinator, entry),
        ]
    )


class ToloFlowInBinarySensor(ToloSaunaCoordinatorEntity, BinarySensorEntity):
    """Water In Valve Sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Water In Valve"
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_icon = "mdi:water-plus-outline"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
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
    _attr_name = "Water Out Valve"
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_icon = "mdi:water-minus-outline"

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Water Out Valve entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_flow_out"

    @property
    def is_on(self) -> bool:
        """Return if flow out valve is open."""
        return self.coordinator.data.status.flow_out
