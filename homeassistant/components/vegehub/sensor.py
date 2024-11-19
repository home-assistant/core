"""Sensor configuration for VegeHub integration."""

from vegehub import therm200_transform, vh400_transform

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHAN_TYPE_BATTERY,
    CHAN_TYPE_SENSOR,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    OPTION_DATA_TYPE_CHOICES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vegetronix sensors from a config entry."""
    sensors = []
    mac_address = str(config_entry.data.get("mac_address"))
    ip_addr = str(config_entry.data.get("ip_addr"))
    num_sensors = int(config_entry.data.get("hub", {}).get("num_channels") or 0)
    is_ac = int(config_entry.data.get("hub", {}).get("is_ac") or 0)

    # We add up the number of sensors, plus the number of actuators, then add one
    # for battery reading, and one because the array is 1 based instead of 0 based.
    for i in range(num_sensors + 1):  # Add 1 for battery
        if i > num_sensors:  # Now we're into actuators
            continue  # Those will be taken care of by switch.py

        if i == num_sensors and is_ac:
            # Skipping battery slot for AC hub
            continue

        chan_type = CHAN_TYPE_SENSOR
        if i == num_sensors:
            chan_type = CHAN_TYPE_BATTERY

        sensor = VegeHubSensor(
            mac_address=mac_address,
            slot=i + 1,
            ip_addr=ip_addr,
            dev_name=str(config_entry.data.get("hostname")),
            data_type=str(config_entry.options.get(f"data_type_{i + 1}", None)),
            chan_type=chan_type,
        )

        hass.data[DOMAIN][sensor.unique_id] = sensor

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
        data_type: str,
        chan_type: str,
    ) -> None:
        """Initialize the sensor."""
        new_id = (
            f"vegehub_{mac_address}_{slot}".lower()
        )  # Generate a unique_id using mac and slot

        self._attr_has_entity_name = True
        self._attr_translation_placeholders = {"index": str(slot)}
        self._data_type: str = data_type
        self._unit_of_measurement: str = ""
        self._attr_native_value = None

        if chan_type == CHAN_TYPE_BATTERY:
            self._unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_translation_key = "battery"
        elif data_type == OPTION_DATA_TYPE_CHOICES[1]:
            self._unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.MOISTURE
            self._attr_translation_key = "vh400_sensor"
        elif data_type == OPTION_DATA_TYPE_CHOICES[2]:
            self._unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_translation_key = "therm200_temp"
        else:
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
        if (
            self._data_type == OPTION_DATA_TYPE_CHOICES[1] and self._attr_native_value
        ):  # Percentage
            return vh400_transform(self._attr_native_value)
        if (
            self._data_type == OPTION_DATA_TYPE_CHOICES[2] and self._attr_native_value
        ):  # Temperature C
            return therm200_transform(self._attr_native_value)

        if isinstance(self._attr_native_value, (int, str, float)):
            return float(self._attr_native_value)
        return None

    async def async_update_sensor(self, value):
        """Update the sensor state with the latest value."""

        self._attr_native_value = value
        self.async_write_ha_state()
