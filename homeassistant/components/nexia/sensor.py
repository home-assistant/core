from homeassistant.const import (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from . import (DATA_NEXIA, ATTR_MODEL, ATTR_FIRMWARE, ATTR_THERMOSTAT_NAME, ATTRIBUTION)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up sensors for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA]

    sensors = list()

    if thermostat.has_variable_speed_compressor():
        sensors.append(NexiaSensor(thermostat, "get_compressor_speed", "Compressor Speed", None, "%", percent_conv))
    # The fan speed reported is actually what the set fan speed is, not the current fan speed.
    # if thermostat.has_variable_fan_speed():
    #     sensors.append(NexiaSensor(thermostat, "get_fan_speed", "nexia_fan_speed", None, "%", percent_conv))
    if thermostat.has_outdoor_temperature():
        unit = (TEMP_CELSIUS if thermostat.get_unit() == 'C' else TEMP_FAHRENHEIT)
        sensors.append(NexiaSensor(thermostat, "get_outdoor_temperature", "Outdoor Temperature", DEVICE_CLASS_TEMPERATURE, unit))
    if thermostat.has_relative_humidity():
        sensors.append(NexiaSensor(thermostat, "get_relative_humidity", "Relative Humidity", DEVICE_CLASS_HUMIDITY, "%", percent_conv))

    add_entities(sensors, True)


ATTR_FAN_SPEED = 'fan_speed'
ATTR_COMPRESSOR_SPEED = 'compressor_speed'
ATTR_OUTDOOR_TEMPERATURE = 'outdoor_temperature'

def percent_conv(val):
    return val * 100.0


class NexiaSensor(Entity):

    def __init__(self, device, sensor_call, sensor_name, sensor_class, sensor_unit, modifier=None):
        """Initialize the sensor."""
        self._device = device
        self._call = sensor_call
        self._name = sensor_name
        self._class = sensor_class
        self._state = None
        self._unit_of_measurement = sensor_unit
        self._modifier = modifier

    @property
    def name(self):
        """Return the name of the Ecobee sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""

        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_MODEL: self._device.get_thermostat_model(),
            ATTR_FIRMWARE: self._device.get_thermostat_firmware(),
            ATTR_THERMOSTAT_NAME: self._device.get_thermostat_name()
        }
        return data

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._class

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self._device, self._call)()
        if self._modifier:
            val = self._modifier(val)
        if type(val) is float:
            val = round(val, 1)
        return val

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self):
        self._device.update()