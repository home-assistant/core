"""Support for MotionMount sensors."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MotionMountEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Vogel's MotionMount from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MotionMountExtensionSensor(coordinator, entry.entry_id),
            MotionMountTurnSensor(coordinator, entry.entry_id),
            MotionMountTargetExtensionSensor(coordinator, entry.entry_id),
            MotionMountTargetTurnSensor(coordinator, entry.entry_id),
            MotionMountErrorStatusSensor(coordinator, entry.entry_id),
        ]
    )


class MotionMountExtensionSensor(MotionMountEntity, SensorEntity):
    """The extension sensor of a MotionMount."""

    _attr_name = "Extension"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-extension"

    @callback
    def _handle_coordinator_update(self) -> None:
        # TODO: Should I check whether the value is actually updated to just the same?
        self._attr_native_value = self.coordinator.data["extension"]
        self.async_write_ha_state()


class MotionMountTurnSensor(MotionMountEntity, SensorEntity):
    """The turn sensor of a MotionMount."""

    _attr_name = "Turn"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-turn"

    @callback
    def _handle_coordinator_update(self) -> None:
        # TODO: Should I check whether the value is actually updated to just the same?
        self._attr_native_value = self.coordinator.data["turn"]
        self.async_write_ha_state()


class MotionMountTargetExtensionSensor(MotionMountEntity, SensorEntity):
    """The target extension sensor of a MotionMount."""

    _attr_name = "Target Extension"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-target-extension"

    @callback
    def _handle_coordinator_update(self) -> None:
        # TODO: Should I check whether the value is actually updated to just the same?
        self._attr_native_value = self.coordinator.data["target_extension"]
        self.async_write_ha_state()


class MotionMountTargetTurnSensor(MotionMountEntity, SensorEntity):
    """The target turn sensor of a MotionMount."""

    _attr_name = "Target Turn"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-target-turn"

    @callback
    def _handle_coordinator_update(self) -> None:
        # TODO: Should I check whether the value is actually updated to just the same?
        self._attr_native_value = self.coordinator.data["target_turn"]
        self.async_write_ha_state()


class MotionMountErrorStatusSensor(MotionMountEntity, SensorEntity):
    """The error status sensor of a MotionMount."""

    _attr_name = "Error Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["None", "Motor", "Internal"]

    def __init__(self, coordinator, unique_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{unique_id}-error-status"

    @callback
    def _handle_coordinator_update(self) -> None:
        # TODO: Should I check whether the value is actually updated to just the same?
        errors = self.coordinator.data["error_status"]

        if errors & (1 << 31):
            # Only when but 31 is set are there any errors active at this moment
            if errors & (1 << 10):
                self._attr_native_value = "Motor"
            else:
                self._attr_native_value = "Internal"
        else:
            self._attr_native_value = "None"
        self.async_write_ha_state()
