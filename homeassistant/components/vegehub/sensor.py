"""Sensor configuration for VegeHub integration."""

from typing import Any

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

        name = f"VegeHub Sensor {i + 1}"

        chan_type = CHAN_TYPE_SENSOR
        if i == num_sensors:
            name = "Battery"
            chan_type = CHAN_TYPE_BATTERY

        sensor = VegeHubSensor(
            name=name,
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
        name: str,
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

        self._attr_name: str = name
        self._data_type: str = data_type
        self._unit_of_measurement: str = ""
        self._attr_native_value = None

        if chan_type == CHAN_TYPE_BATTERY:
            self._unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif data_type == OPTION_DATA_TYPE_CHOICES[1]:
            self._unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.MOISTURE
        elif data_type == OPTION_DATA_TYPE_CHOICES[2]:
            self._unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        else:
            self._unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_device_class = SensorDeviceClass.VOLTAGE

        self._mac_address: str = mac_address
        self._slot: int = slot
        self._attr_unique_id: str = new_id
        self.entity_id: str = "sensor." + new_id
        self._ip_addr: str = ip_addr
        self._dev_name: str = dev_name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if (
            self._data_type == OPTION_DATA_TYPE_CHOICES[1] and self._attr_native_value
        ):  # Percentage
            return VH400_transform(self._attr_native_value)
        if (
            self._data_type == OPTION_DATA_TYPE_CHOICES[2] and self._attr_native_value
        ):  # Temperature C
            if isinstance(self._attr_native_value, (int, str, float)):
                return (41.6700 * float(self._attr_native_value)) - 40.0000
            return None

        if isinstance(self._attr_native_value, (int, str, float)):
            return float(self._attr_native_value)
        return None

    @property
    def suggested_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this sensor."""
        return self._attr_device_class

    @property
    def suggested_display_precision(self) -> int:
        """Return the suggested display precision of this sensor."""
        return 2

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac_address)},
            name=self._dev_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_update_sensor(self, value):
        """Update the sensor state with the latest value."""

        self._attr_native_value = value
        self.async_write_ha_state()


def VH400_transform(x: Any) -> float:
    """Perform a piecewise linear transformation on the input value `x`.

    The transform is based on the following pairs of points:
    (0,0), (1.1000, 10.0000), (1.3000, 15.0000), (1.8200, 40.0000),
    (2.2000, 50.0000), (3.0000, 100.0000)
    """
    if isinstance(x, (int, str)):
        x = float(x)

    if not isinstance(x, float):
        return 0.0

    if x <= 0.0100:
        # Below 0.01V is just noise and should be reported as 0
        return 0
    if x <= 1.1000:
        # Linear interpolation between (0.0000, 0.0000) and (1.1000, 10.0000)
        return (10.0000 - 0.0000) / (1.1000 - 0.0000) * (x - 0.0000) + 0.0000
    if x <= 1.3000:
        # Linear interpolation between (1.1000, 10.0000) and (1.3000, 15.0000)
        return (15.0000 - 10.0000) / (1.3000 - 1.1000) * (x - 1.1000) + 10.0000
    if x <= 1.8200:
        # Linear interpolation between (1.3000, 15.0000) and (1.8200, 40.0000)
        return (40.0000 - 15.0000) / (1.8200 - 1.3000) * (x - 1.3000) + 15.0000
    if x <= 2.2000:
        # Linear interpolation between (1.8200, 40.0000) and (2.2000, 50.0000)
        return (50.0000 - 40.0000) / (2.2000 - 1.8200) * (x - 1.8200) + 40.0000
    if x <= 3.0000:
        # Linear interpolation between (2.2000, 50.0000) and (3.0000, 100.0000)
        return (100.0000 - 50.0000) / (3.0000 - 2.2000) * (x - 2.2000) + 50.0000

    # For values greater than 3.0000, return 100.0000
    return 100.0000
