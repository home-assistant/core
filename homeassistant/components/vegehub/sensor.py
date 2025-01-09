"""Sensor configuration for VegeHub integration."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import VegeHubCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vegetronix sensors from a config entry."""
    sensors = []
    mac_address = config_entry.data[CONF_MAC]
    num_sensors = config_entry.runtime_data.hub.num_sensors
    num_actuators = config_entry.runtime_data.hub.num_actuators

    # We add up the number of sensors, plus the number of actuators, then add one
    # for battery reading, and one because the array is 1 based instead of 0 based.
    for i in range(num_sensors + num_actuators + 1):  # Add 1 for battery
        sensor = VegeHubSensor(
            mac_address=mac_address,
            slot=i + 1,
            dev_name=config_entry.data[CONF_HOST],
            coordinator=config_entry.runtime_data.coordinator,
        )

        # Store the entity by ID in runtime_data hub
        config_entry.runtime_data.hub.entities[sensor.unique_id] = sensor

        sensors.append(sensor)

    if sensors:
        async_add_entities(sensors)


class VegeHubSensor(CoordinatorEntity, SensorEntity):
    """Class for VegeHub Analog Sensors."""

    def __init__(
        self,
        mac_address: str,
        slot: int,
        dev_name: str,
        coordinator: VegeHubCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_translation_placeholders = {"index": str(slot)}

        self._unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_translation_key = "analog_sensor"
        self.latest_value: float | None = None

        self._attr_suggested_unit_of_measurement = self._unit_of_measurement
        self._attr_native_unit_of_measurement = self._unit_of_measurement
        self._mac_address: str = mac_address
        self._attr_unique_id: str = (
            f"vegehub_{mac_address}_{slot}".lower()
        )  # Generate a unique_id using mac and slot
        self._attr_suggested_display_precision = 2
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac_address)},
            name=dev_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._attr_unique_id)
        # Only set a new value if there is one available in the coordinator.
        if value is not None:
            self.latest_value = value
        return self.latest_value
