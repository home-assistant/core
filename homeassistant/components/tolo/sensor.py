"""TOLO Sauna (non-binary, general) sensors."""

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up (non-binary, general) sensors for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ToloWaterLevelSensor(coordinator, entry),
            ToloTankTemperatureSensor(coordinator, entry),
        ]
    )


class ToloWaterLevelSensor(ToloSaunaCoordinatorEntity, SensorEntity):
    """Sensor for tank water level."""

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
    _attr_name = "Water Level"
    _attr_icon = "mdi:waves-arrow-up"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Sauna tank water level sensor entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_water_level"

    @property
    def native_value(self) -> int:
        """Return current tank water level."""
        return self.coordinator.data.status.water_level_percent


class ToloTankTemperatureSensor(ToloSaunaCoordinatorEntity, SensorEntity):
    """Sensor for tank temperature."""

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
    _attr_name = "Tank Temperature"
    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Sauna tank temperature sensor entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_tank_temperature"

    @property
    def native_value(self) -> int:
        """Return current tank temperature."""
        return self.coordinator.data.status.tank_temperature
