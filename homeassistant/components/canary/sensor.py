"""Support for Canary sensors."""
from canary.api import SensorType

from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import DATA_CANARY

SENSOR_VALUE_PRECISION = 2
ATTR_AIR_QUALITY = "air_quality"

# Define variables to store the device names, as referred to by the Canary API.
# Note: If Canary change the name of any of their devices (which they have done),
# then these variables will need updating, otherwise the sensors will stop working
# and disappear in Home Assistant.
CANARY_PRO = "Canary Pro"
CANARY_FLEX = "Canary Flex"

# Sensor types are defined like so:
# sensor type name, unit_of_measurement, icon
SENSOR_TYPES = [
    ["temperature", TEMP_CELSIUS, "mdi:thermometer", [CANARY_PRO]],
    ["humidity", UNIT_PERCENTAGE, "mdi:water-percent", [CANARY_PRO]],
    ["air_quality", None, "mdi:weather-windy", [CANARY_PRO]],
    ["wifi", "dBm", "mdi:wifi", [CANARY_FLEX]],
    ["battery", UNIT_PERCENTAGE, "mdi:battery-50", [CANARY_FLEX]],
]

STATE_AIR_QUALITY_NORMAL = "normal"
STATE_AIR_QUALITY_ABNORMAL = "abnormal"
STATE_AIR_QUALITY_VERY_ABNORMAL = "very_abnormal"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        for device in location.devices:
            if device.is_online:
                device_type = device.device_type
                for sensor_type in SENSOR_TYPES:
                    if device_type.get("name") in sensor_type[3]:
                        devices.append(
                            CanarySensor(data, sensor_type, location, device)
                        )

    add_entities(devices, True)


class CanarySensor(Entity):
    """Representation of a Canary sensor."""

    def __init__(self, data, sensor_type, location, device):
        """Initialize the sensor."""
        self._data = data
        self._sensor_type = sensor_type
        self._device_id = device.device_id
        self._sensor_value = None

        sensor_type_name = sensor_type[0].replace("_", " ").title()
        self._name = f"{location.name} {device.name} {sensor_type_name}"

    @property
    def name(self):
        """Return the name of the Canary sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sensor_value

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device_id}_{self._sensor_type[0]}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor_type[1]

    @property
    def icon(self):
        """Icon for the sensor."""
        if self.state is not None and self._sensor_type[0] == "battery":
            return icon_for_battery_level(battery_level=self.state)

        return self._sensor_type[2]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._sensor_type[0] == "air_quality" and self._sensor_value is not None:
            air_quality = None
            if self._sensor_value <= 0.4:
                air_quality = STATE_AIR_QUALITY_VERY_ABNORMAL
            elif self._sensor_value <= 0.59:
                air_quality = STATE_AIR_QUALITY_ABNORMAL
            elif self._sensor_value <= 1.0:
                air_quality = STATE_AIR_QUALITY_NORMAL

            return {ATTR_AIR_QUALITY: air_quality}

        return None

    def update(self):
        """Get the latest state of the sensor."""
        self._data.update()

        canary_sensor_type = None
        if self._sensor_type[0] == "air_quality":
            canary_sensor_type = SensorType.AIR_QUALITY
        elif self._sensor_type[0] == "temperature":
            canary_sensor_type = SensorType.TEMPERATURE
        elif self._sensor_type[0] == "humidity":
            canary_sensor_type = SensorType.HUMIDITY
        elif self._sensor_type[0] == "wifi":
            canary_sensor_type = SensorType.WIFI
        elif self._sensor_type[0] == "battery":
            canary_sensor_type = SensorType.BATTERY

        value = self._data.get_reading(self._device_id, canary_sensor_type)

        if value is not None:
            self._sensor_value = round(float(value), SENSOR_VALUE_PRECISION)
