"""Sensor configuration for VegeHub integration."""

from itertools import count

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VegeHubConfigEntry, VegeHubCoordinator
from .entity import VegeHubEntity

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "analog_sensor": SensorEntityDescription(
        key="analog_sensor",
        translation_key="analog_sensor",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VegeHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vegetronix sensors from a config entry."""
    sensors: list[VegeHubSensor] = []
    coordinator = config_entry.runtime_data

    # This is the index in the updates from the VegeHub that will correspond to
    # each sensor. This index is 1-based.
    update_index = count(1)

    # Add each analog sensor input
    for _i in range(coordinator.vegehub.num_sensors):
        sensor = VegeHubSensor(
            index=next(update_index),
            coordinator=coordinator,
            description=SENSOR_TYPES["analog_sensor"],
        )
        sensors.append(sensor)

    # Add the battery sensor
    sensors.append(
        VegeHubSensor(
            index=next(update_index),
            coordinator=coordinator,
            description=SENSOR_TYPES["battery"],
        )
    )

    async_add_entities(sensors)


class VegeHubSensor(VegeHubEntity, SensorEntity):
    """Class for VegeHub Analog Sensors."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        index: int,
        coordinator: VegeHubCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Set unique ID for pulling data from the coordinator
        self._attr_unique_id = f"{self._mac_address}_{index}".lower()
        if description.key == "analog_sensor":
            self._attr_translation_placeholders = {"index": str(index)}
        self._attr_available = False

    @property
    def native_value(self) -> float | None:
        """Return the sensor's current value."""
        if self.coordinator.data is None or self._attr_unique_id is None:
            return None
        return self.coordinator.data.get(self._attr_unique_id)
