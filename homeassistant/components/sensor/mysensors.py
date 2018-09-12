"""
Support for MySensors sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

SENSORS = {
    'V_TEMP': [None, 'mdi:thermometer'],
    'V_HUM': ['%', 'mdi:water-percent'],
    'V_DIMMER': ['%', 'mdi:percent'],
    'V_LIGHT_LEVEL': ['%', 'white-balance-sunny'],
    'V_DIRECTION': ['°', 'mdi:compass'],
    'V_WEIGHT': ['kg', 'mdi:weight-kilogram'],
    'V_DISTANCE': ['m', 'mdi:ruler'],
    'V_IMPEDANCE': ['ohm', None],
    'V_WATT': ['W', None],
    'V_KWH': ['kWh', None],
    'V_FLOW': ['m', None],
    'V_VOLUME': ['m³', None],
    'V_VOLTAGE': ['V', 'mdi:flash'],
    'V_CURRENT': ['A', 'mdi:flash-auto'],
    'V_PERCENTAGE': ['%', 'mdi:percent'],
    'V_LEVEL': {
        'S_SOUND': ['dB', 'mdi:volume-high'], 'S_VIBRATION': ['Hz', None],
        'S_LIGHT_LEVEL': ['lx', 'white-balance-sunny']},
    'V_ORP': ['mV', None],
    'V_EC': ['μS/cm', None],
    'V_VAR': ['var', None],
    'V_VA': ['VA', None],
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the MySensors platform for sensors."""
    mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsSensor,
        async_add_entities=async_add_entities)


class MySensorsSensor(mysensors.device.MySensorsEntity):
    """Representation of a MySensors Sensor child node."""

    @property
    def force_update(self):
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return True

    @property
    def state(self):
        """Return the state of the device."""
        return self._values.get(self.value_type)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        _, icon = self._get_sensor_type()
        return icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        set_req = self.gateway.const.SetReq
        if (float(self.gateway.protocol_version) >= 1.5 and
                set_req.V_UNIT_PREFIX in self._values):
            return self._values[set_req.V_UNIT_PREFIX]
        unit, _ = self._get_sensor_type()
        return unit

    def _get_sensor_type(self):
        """Return list with unit and icon of sensor type."""
        pres = self.gateway.const.Presentation
        set_req = self.gateway.const.SetReq
        SENSORS[set_req.V_TEMP.name][0] = (
            TEMP_CELSIUS if self.gateway.metric else TEMP_FAHRENHEIT)
        sensor_type = SENSORS.get(set_req(self.value_type).name, [None, None])
        if isinstance(sensor_type, dict):
            sensor_type = sensor_type.get(
                pres(self.child_type).name, [None, None])
        return sensor_type
