"""Sensor configuration for VegeHub integration."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, MODEL


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vegetronix sensors from a config entry."""
    sensors = []
    mac_address = config_entry.data[CONF_MAC]
    ip_addr = config_entry.data[CONF_IP_ADDRESS]
    num_sensors = config_entry.runtime_data.num_sensors
    num_actuators = config_entry.runtime_data.num_actuators

    # We add up the number of sensors, plus the number of actuators, then add one
    # for battery reading, and one because the array is 1 based instead of 0 based.
    for i in range(num_sensors + num_actuators + 1):  # Add 1 for battery
        sensor = VegeHubSensor(
            mac_address=mac_address,
            slot=i + 1,
            ip_addr=ip_addr,
            dev_name=config_entry.data[CONF_HOST],
        )

        # Store the entity by ID in runtime_data
        config_entry.runtime_data.entities[sensor.unique_id] = sensor

        sensors.append(sensor)

    if sensors:
        async_add_entities(sensors)


class VegeHubSensor(SensorEntity):
    """Class for VegeHub Analog Sensors."""

    def __init__(
        self,
        mac_address: str,
        slot: int,
        ip_addr: str,
        dev_name: str,
    ) -> None:
        """Initialize the sensor."""
        new_id = (
            f"vegehub_{mac_address}_{slot}".lower()
        )  # Generate a unique_id using mac and slot

        self._attr_has_entity_name = True
        self._attr_translation_placeholders = {"index": str(slot)}
        self._unit_of_measurement: str = ""
        self._attr_native_value = None

        self._unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_translation_key = "analog_sensor"

        self._attr_suggested_unit_of_measurement = self._unit_of_measurement
        self._attr_native_unit_of_measurement = self._unit_of_measurement
        self._mac_address: str = mac_address
        self._slot: int = slot
        self._attr_unique_id: str = new_id
        self._ip_addr: str = ip_addr
        self._dev_name: str = dev_name
        self._attr_suggested_display_precision = 2
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac_address)},
            name=self._dev_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if isinstance(self._attr_native_value, (int, str, float)):
            return float(self._attr_native_value)
        return None

    async def async_update_sensor(self, value):
        """Update the sensor state with the latest value."""

        self._attr_native_value = value
        self.async_write_ha_state()
