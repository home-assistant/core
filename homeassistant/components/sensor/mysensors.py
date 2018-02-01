"""
Support for MySensors sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.sensor import DOMAIN
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MySensors platform for sensors."""
    mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsSensor, add_devices=add_devices)


class MySensorsSensor(mysensors.MySensorsEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        pres = self.gateway.const.Presentation
        set_req = self.gateway.const.SetReq
        unit_map = {
            set_req.V_TEMP: (TEMP_CELSIUS
                             if self.gateway.metric else TEMP_FAHRENHEIT),
            set_req.V_HUM: '%',
            set_req.V_DIMMER: '%',
            set_req.V_LIGHT_LEVEL: '%',
            set_req.V_DIRECTION: '°',
            set_req.V_WEIGHT: 'kg',
            set_req.V_DISTANCE: 'm',
            set_req.V_IMPEDANCE: 'ohm',
            set_req.V_WATT: 'W',
            set_req.V_KWH: 'kWh',
            set_req.V_FLOW: 'm',
            set_req.V_VOLUME: 'm³',
            set_req.V_VOLTAGE: 'V',
            set_req.V_CURRENT: 'A',
        }
        if float(self.gateway.protocol_version) >= 1.5:
            if set_req.V_UNIT_PREFIX in self._values:
                return self._values[
                    set_req.V_UNIT_PREFIX]
            unit_map.update({
                set_req.V_PERCENTAGE: '%',
                set_req.V_LEVEL: {
                    pres.S_SOUND: 'dB', pres.S_VIBRATION: 'Hz',
                    pres.S_LIGHT_LEVEL: 'lux'}})
        if float(self.gateway.protocol_version) >= 2.0:
            unit_map.update({
                set_req.V_ORP: 'mV',
                set_req.V_EC: 'μS/cm',
                set_req.V_VAR: 'var',
                set_req.V_VA: 'VA',
            })
        unit = unit_map.get(self.value_type)
        if isinstance(unit, dict):
            unit = unit.get(self.child_type)
        return unit
