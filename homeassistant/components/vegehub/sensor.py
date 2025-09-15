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
    "battery_volts": SensorEntityDescription(
        key="battery_volts",
        translation_key="battery_volts",
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

    sensor_index = count(0)

    # Add each analog sensor input
    for _i in range(coordinator.vegehub.num_sensors):
        sensor = VegeHubSensor(
            index=next(sensor_index),
            coordinator=coordinator,
            description=SENSOR_TYPES["analog_sensor"],
        )
        sensors.append(sensor)

    # Add the battery sensor
    if not coordinator.vegehub.is_ac:
        sensors.append(
            VegeHubSensor(
                index=next(sensor_index),
                coordinator=coordinator,
                description=SENSOR_TYPES["battery_volts"],
            )
        )

    async_add_entities(sensors)


class VegeHubSensor(VegeHubEntity, SensorEntity):
    """Class for VegeHub Analog Sensors."""

    def __init__(
        self,
        index: int,
        coordinator: VegeHubCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Set data key for pulling data from the coordinator
        if description.key == "battery_volts":
            self.data_key = "battery"
        else:
            self.data_key = f"analog_{index}"
            self._attr_translation_placeholders = {"index": str(index + 1)}
        self._attr_unique_id = f"{self._mac_address}_{self.data_key}"
        self._attr_available = False

    @property
    def native_value(self) -> float | None:
        """Return the sensor's current value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.data_key)
