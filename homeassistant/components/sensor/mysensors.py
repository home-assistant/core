"""
Support for MySensors sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors/
"""
import logging

from homeassistant.components import mysensors
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MySensors platform for sensors."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if not gateways:
        return

    for gateway in gateways:
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_TEMP: [set_req.V_TEMP],
            pres.S_HUM: [set_req.V_HUM],
            pres.S_BARO: [set_req.V_PRESSURE, set_req.V_FORECAST],
            pres.S_WIND: [set_req.V_WIND, set_req.V_GUST, set_req.V_DIRECTION],
            pres.S_RAIN: [set_req.V_RAIN, set_req.V_RAINRATE],
            pres.S_UV: [set_req.V_UV],
            pres.S_WEIGHT: [set_req.V_WEIGHT, set_req.V_IMPEDANCE],
            pres.S_POWER: [set_req.V_WATT, set_req.V_KWH],
            pres.S_DISTANCE: [set_req.V_DISTANCE],
            pres.S_LIGHT_LEVEL: [set_req.V_LIGHT_LEVEL],
            pres.S_IR: [set_req.V_IR_RECEIVE],
            pres.S_WATER: [set_req.V_FLOW, set_req.V_VOLUME],
            pres.S_CUSTOM: [set_req.V_VAR1,
                            set_req.V_VAR2,
                            set_req.V_VAR3,
                            set_req.V_VAR4,
                            set_req.V_VAR5],
            pres.S_SCENE_CONTROLLER: [set_req.V_SCENE_ON,
                                      set_req.V_SCENE_OFF],
        }
        if float(gateway.protocol_version) < 1.5:
            map_sv_types.update({
                pres.S_AIR_QUALITY: [set_req.V_DUST_LEVEL],
                pres.S_DUST: [set_req.V_DUST_LEVEL],
            })
        if float(gateway.protocol_version) >= 1.5:
            map_sv_types.update({
                pres.S_COLOR_SENSOR: [set_req.V_RGB],
                pres.S_MULTIMETER: [set_req.V_VOLTAGE,
                                    set_req.V_CURRENT,
                                    set_req.V_IMPEDANCE],
                pres.S_SOUND: [set_req.V_LEVEL],
                pres.S_VIBRATION: [set_req.V_LEVEL],
                pres.S_MOISTURE: [set_req.V_LEVEL],
                pres.S_AIR_QUALITY: [set_req.V_LEVEL],
                pres.S_DUST: [set_req.V_LEVEL],
            })
            map_sv_types[pres.S_LIGHT_LEVEL].append(set_req.V_LEVEL)

        if float(gateway.protocol_version) >= 2.0:
            map_sv_types.update({
                pres.S_INFO: [set_req.V_TEXT],
                pres.S_GAS: [set_req.V_FLOW, set_req.V_VOLUME],
                pres.S_GPS: [set_req.V_POSITION],
                pres.S_WATER_QUALITY: [set_req.V_TEMP, set_req.V_PH,
                                       set_req.V_ORP, set_req.V_EC]
            })
            map_sv_types[pres.S_CUSTOM].append(set_req.V_CUSTOM)
            map_sv_types[pres.S_POWER].extend(
                [set_req.V_VAR, set_req.V_VA, set_req.V_POWER_FACTOR])

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, MySensorsSensor, add_devices))


class MySensorsSensor(mysensors.MySensorsDeviceEntity, Entity):
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
