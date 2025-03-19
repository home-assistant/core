"""Sensor configuration for VegeHub integration."""

from itertools import count

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VegeHubCoordinator
from .entity import VegeHubEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
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
        )
        sensors.append(sensor)

    # Add the battery sensor
    sensors.append(
        VegeHubSensor(
            index=next(update_index),
            coordinator=coordinator,
            translation_key="battery",
        )
    )

    async_add_entities(sensors)


class VegeHubSensor(VegeHubEntity, SensorEntity):
    """Class for VegeHub Analog Sensors."""

    _attr_has_entity_name = True
    _unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = _unit_of_measurement
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        index: int,
        coordinator: VegeHubCoordinator,
        translation_key: str = "analog_sensor",
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = translation_key
        if translation_key == "analog_sensor":
            self._attr_translation_placeholders = {"index": str(index)}
        self._attr_available = False
        self._attr_unique_id = (
            f"{self._mac_address}_{index}".lower()
        )  # Set unique ID for pulling data from the coordinator

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.coordinator.data is not None
            and self._attr_unique_id is not None
            and self._attr_unique_id in self.coordinator.data
        ):
            self._attr_native_value = self.coordinator.data[self._attr_unique_id]
            self._attr_available = True
        super()._handle_coordinator_update()
