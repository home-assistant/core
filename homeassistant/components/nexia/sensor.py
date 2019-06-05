from homeassistant.const import (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from . import (DATA_NEXIA, ATTR_MODEL, ATTR_FIRMWARE, ATTR_THERMOSTAT_NAME, ATTRIBUTION, )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up sensors for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA]

    sensors = list()

    sensors.append(NexiaSensor(thermostat, "get_system_status", "System Status", None, None))

    if thermostat.has_variable_speed_compressor():
        sensors.append(NexiaSensor(thermostat, "get_current_compressor_speed", "Current Compressor Speed", None, "%",
                                   percent_conv))
        sensors.append(NexiaSensor(thermostat, "get_requested_compressor_speed", "Requested Compressor Speed", None,
                                   "%", percent_conv))

    if thermostat.has_outdoor_temperature():
        unit = (TEMP_CELSIUS if thermostat.get_unit() == thermostat.UNIT_CELSIUS else TEMP_FAHRENHEIT)
        sensors.append(NexiaSensor(thermostat, "get_outdoor_temperature", "Outdoor Temperature",
                                   DEVICE_CLASS_TEMPERATURE, unit))

    if thermostat.has_relative_humidity():
        sensors.append(NexiaSensor(thermostat, "get_relative_humidity", "Relative Humidity", DEVICE_CLASS_HUMIDITY,
                                   "%", percent_conv))

    for zone in thermostat.get_zone_ids():
        name = thermostat.get_zone_name(zone)
        unit = (TEMP_CELSIUS if thermostat.get_unit() == thermostat.UNIT_CELSIUS else TEMP_FAHRENHEIT)
        sensors.append(NexiaZoneSensor(thermostat, zone, "get_zone_temperature", f"{name} Temperature",
                                       DEVICE_CLASS_TEMPERATURE, unit, None))
        sensors.append(NexiaZoneSensor(thermostat, zone, "get_zone_status", f"{name} Zone Status", None, None))
        sensors.append(NexiaZoneSensor(thermostat, zone, "get_zone_setpoint_status", f"{name} Zone Setpoint Status",
                                       None, None))




    add_entities(sensors, True)



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
        self.update = Throttle(self._device.update_rate)(self._update)


    @property
    def name(self):
        """Return the name of the sensor."""
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

    def _update(self):
        self._device.update()


class NexiaZoneSensor(NexiaSensor):
    def __init__(self, device, zone, sensor_call, sensor_name, sensor_class, sensor_unit, modifier=None):
        super().__init__(device, sensor_call, sensor_name, sensor_class, sensor_unit, modifier)
        self.zone = zone

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self._device, self._call)(self.zone)
        if self._modifier:
            val = self._modifier(val)
        if type(val) is float:
            val = round(val, 1)
        return val
