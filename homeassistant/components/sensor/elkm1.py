"""
Support for control of ElkM1 sensors. On the ElkM1 there are 5 types
of sensors:
- Zones that are on/off/voltage/temperature.
- Keypads that have temperature (not all models, but no way to know)
- Counters that are integers that can be read/set
- Settings that are used to trigger automations

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.elkm1/
"""

import voluptuous as vol

from homeassistant.const import (ATTR_ENTITY_ID, STATE_UNKNOWN,
                                 TEMP_FAHRENHEIT)
import homeassistant.components.sensor as sensor

from homeassistant.components.elkm1 import (DOMAIN, create_elk_devices,
                                            ElkDeviceBase,
                                            register_elk_service)
import homeassistant.helpers.config_validation as cv

from elkm1_lib.const import (ElkRPStatus, SettingFormat, ZoneLogicalStatus,
                             ZonePhysicalStatus, ZoneType)
from elkm1_lib.util import pretty_const, username

DEPENDENCIES = [DOMAIN]

SPEAK_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required('number'): vol.Range(min=0, max=999),
})

_ZONE_ICONS = {
    ZoneType.FIRE_ALARM.value: 'fire',
    ZoneType.FIRE_VERIFIED.value: 'fire',
    ZoneType.FIRE_SUPERVISORY.value: 'fire',
    ZoneType.KEYFOB.value: 'key',
    ZoneType.NON_ALARM.value: 'alarm-off',
    ZoneType.MEDICAL_ALARM.value: 'medical-bag',
    ZoneType.POLICE_ALARM.value: 'alarm-light',
    ZoneType.POLICE_NO_INDICATION.value: 'alarm-light',
    ZoneType.KEY_MOMENTARY_ARM_DISARM.value: 'power',
    ZoneType.KEY_MOMENTARY_ARM_AWAY.value: 'power',
    ZoneType.KEY_MOMENTARY_ARM_STAY.value: 'power',
    ZoneType.KEY_MOMENTARY_DISARM.value: 'power',
    ZoneType.KEY_ON_OFF.value: 'toggle-switch',
    ZoneType.MUTE_AUDIBLES.value: 'volume-mute',
    ZoneType.POWER_SUPERVISORY.value: 'power-plug',
    ZoneType.TEMPERATURE.value: 'thermometer-lines',
    ZoneType.ANALOG_ZONE.value: 'speedometer',
    ZoneType.PHONE_KEY.value: 'phone-classic',
    ZoneType.INTERCOM_KEY.value: 'deskphone'
}


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info):
    """Setup the Elk sensor platform."""

    elk = hass.data[DOMAIN]['elk']
    devices = create_elk_devices(hass, [elk.panel],
                                 'panel', ElkPanel, [])
    devices = create_elk_devices(hass, elk.zones,
                                 'zone', ElkZone, devices)
    devices = create_elk_devices(hass, elk.keypads,
                                 'keypad', ElkKeypad, devices)
    devices = create_elk_devices(hass, elk.thermostats,
                                 'thermostat', ElkThermostat, devices)
    devices = create_elk_devices(hass, elk.counters,
                                 'counter', ElkCounter, devices)
    devices = create_elk_devices(hass, elk.settings,
                                 'setting', ElkSetting, devices)
    async_add_devices(devices, True)

    register_elk_service(hass, sensor.DOMAIN, 'sensor_speak_word',
                         SPEAK_SERVICE_SCHEMA, 'async_sensor_speak_word')
    register_elk_service(hass, sensor.DOMAIN, 'sensor_speak_phrase',
                         SPEAK_SERVICE_SCHEMA, 'async_sensor_speak_phrase')

    return True


def temperature_to_state(temperature, undef_temperature):
    """Helper to convert a temperature to a state."""
    return temperature if temperature > undef_temperature else STATE_UNKNOWN


class ElkPanel(ElkDeviceBase):
    """Handle an Elk Panel."""
    def __init__(self, device, hass, config):
        ElkDeviceBase.__init__(self, 'sensor', device, hass, config)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:home"

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs['elkm1_version'] = self._element.elkm1_version
        attrs['remote_programming_status'] = ElkRPStatus(
            self._element.remote_programming_status).name.lower()
        attrs['system_trouble_status'] = self._element.system_trouble_status
        attrs['xep_version'] = self._element.xep_version
        return attrs

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        if self._elk.is_connected():
            self._state = 'Paused' if self._element.remote_programming_status \
                else 'Connected'
        else:
            self._state = 'Disconnected'

    async def async_sensor_speak_word(self, number):
        """Speak a word on the panel."""
        self._element.speak_word(number)

    async def async_sensor_speak_phrase(self, number):
        """Speak a phrase on the panel."""
        self._element.speak_phrase(number)


class ElkKeypad(ElkDeviceBase):
    """Handle an Elk Keypad."""
    def __init__(self, device, hass, config):
        ElkDeviceBase.__init__(self, 'sensor', device, hass, config)

    @property
    def temperature_unit(self):
        """The temperature scale."""
        return TEMP_FAHRENHEIT

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return self.temperature_unit

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:thermometer-lines'

    @property
    def device_state_attributes(self):
        """Attributes of the keypad."""
        attrs = self.initial_attrs()
        attrs['area'] = self._element.area + 1
        attrs['temperature'] = self._element.temperature
        attrs['last_user_time'] = self._element.last_user_time.isoformat()
        attrs['last_user'] = self._element.last_user + 1
        attrs['code'] = self._element.code

        attrs['last_user_name'] = username(self._elk, self._element.last_user)
        return attrs

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        self._state = temperature_to_state(self._element.temperature, -40)

    async def async_added_to_hass(self):
        """Register callback for ElkM1 changes and update entity state."""
        await ElkDeviceBase.async_added_to_hass(self)
        self._hass.data[DOMAIN]['keypads'][
            self._element.index] = self.entity_id


class ElkZone(ElkDeviceBase):
    """Handle an Elk Zone."""
    def __init__(self, device, hass, config):
        ElkDeviceBase.__init__(self, 'sensor', device, hass, config)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:' + _ZONE_ICONS.get(self._element.definition, 'alarm-bell')

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs['physical_status'] = ZonePhysicalStatus(
            self._element.physical_status).name.lower()
        attrs['logical_status'] = ZoneLogicalStatus(
            self._element.logical_status).name.lower()
        attrs['definition'] = ZoneType(
            self._element.definition).name.lower()
        attrs['area'] = self._element.area + 1
        attrs['bypassed'] = self._element.bypassed
        attrs['triggered_alarm'] = self._element.triggered_alarm
        if self._element.definition == ZoneType.TEMPERATURE.value:
            attrs['temperature'] = self._element.temperature
        elif self._element.definition == ZoneType.ANALOG_ZONE.value:
            attrs['voltage'] = self._element.voltage
        return attrs

    @property
    def temperature_unit(self):
        """The temperature scale."""
        return self._temperature_unit

    @property
    def unit_of_measurement(self):
        """Unit of measurement."""
        if self._element.definition == ZoneType.TEMPERATURE.value:
            return self.temperature_unit
        if self._element.definition == ZoneType.ANALOG_ZONE.value:
            return 'volts'
        return None

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        if self._element.definition == ZoneType.TEMPERATURE.value:
            self._state = temperature_to_state(self._element.temperature, -60)
        elif self._element.definition == ZoneType.ANALOG_ZONE.value:
            self._state = self._element.voltage
        else:
            self._state = pretty_const(ZoneLogicalStatus(
                self._element.logical_status).name)


class ElkThermostat(ElkDeviceBase):
    """Handle an Elk thermostat."""
    def __init__(self, device, hass, config):
        ElkDeviceBase.__init__(self, 'sensor', device, hass, config)

    @property
    def temperature_unit(self):
        """The temperature scale."""
        return self._temperature_unit

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return self.temperature_unit

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:thermometer-lines'

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        self._state = temperature_to_state(self._element.current_temp, 0)


# pylint: disable=too-few-public-methods
class ElkCounter(ElkDeviceBase):
    """Handle an Elk Counter."""
    def __init__(self, device, hass, config):
        ElkDeviceBase.__init__(self, 'sensor', device, hass, config)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:numeric'

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        self._state = self._element.value


class ElkSetting(ElkDeviceBase):
    """Handle an Elk setting."""
    def __init__(self, device, hass, config):
        ElkDeviceBase.__init__(self, 'sensor', device, hass, config)

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:numeric'

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        self._state = self._element.value

    @property
    def device_state_attributes(self):
        """Attributes of the sensor."""
        attrs = self.initial_attrs()
        attrs['value_format'] = SettingFormat(
            self._element.value_format).name.lower()
        attrs['value'] = self._element.value
        return attrs
