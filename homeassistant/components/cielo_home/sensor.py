"""Support for Cielo Home sensors."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SENSOR_HUMIDITY, SENSOR_TEMPERATURE
from .coordinator import CieloDataUpdateCoordinator, CieloHomeConfigEntry
from .entity import CieloDeviceEntity

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CieloHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cielo Home sensors."""
    coordinator = entry.runtime_data

    entities = [
        CieloSensor(coordinator, device_id, description)
        for device_id in coordinator.data.parsed
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class CieloSensor(CieloDeviceEntity, SensorEntity):
    """Representation of a Cielo Home sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def native_value(self) -> float | int | None:
        """Return the native value of the sensor."""
        if self.entity_description.key == SENSOR_TEMPERATURE:
            # current_temperature() returns None when unavailable.
            return self.client.current_temperature()
        if self.entity_description.key == SENSOR_HUMIDITY:
            return self.device_data.humidity if self.device_data else None
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        if self.entity_description.key == SENSOR_TEMPERATURE:
            return self.temperature_unit
        return super().native_unit_of_measurement
