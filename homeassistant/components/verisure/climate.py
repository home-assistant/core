import logging
import jsonpath
import dateutil.parser
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_SWING_MODE, SUPPORT_ON_OFF)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from . import HUB as hub

jsonpath = jsonpath.jsonpath
_LOGGER = logging.getLogger(__name__)

VERISIRE_HASS_OP_MODE = {
    'AUTO': 'auto',
    'FAN': 'fan_only',
    'COOL': 'cool',
    'DRY': 'dry',
    'HEAT': 'heat'
}

HASS_VERISURE_OP_MODE = {
    'auto': 'AUTO',
    'fan_only': 'FAN',
    'cool': 'COOL',
    'dry': 'DRY',
    'heat': 'HEAT'
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    global heat_pumps
    hub.update_overview()
    heat_pumps = hub.get('$.heatPumps')

    if len(heat_pumps) > 0:
        for heat_pump in heat_pumps[0]:
            device_label = jsonpath(heat_pump, '$.deviceLabel')[0]
            add_entities([
                VerisureHeatPump(device_label)
            ])


class VerisureHeatPump(ClimateDevice):

    def __init__(self, heatpumpid):
        """Initialize the climate device."""
        self.id = heatpumpid
        self._support_flags = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE |\
            SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF | SUPPORT_SWING_MODE
        self._unit_of_measurement = TEMP_CELSIUS
        self._fan_list = ['Auto', 'Low', 'Medium_Low', 'Medium',
                          'Medium_High', 'High']
        self._operation_list = ['heat', 'cool', 'auto', 'dry', 'fan_only']
        self._swing_list = ['Auto', '0_Degrees', '30_Degrees', '60_Degrees',
                            '90_Degrees']
        self._config_date = None
        self.sync_data()

    def sync_data(self):
        global heat_pumps
        hub.update_overview()
        heat_pumps = hub.get('$.heatPumps')[0]
        self.heatpumpstate = jsonpath(heat_pumps, '$.[?(@.deviceLabel == \'' +
                                      self.id + '\')]')[0]
        self._name = jsonpath(self.heatpumpstate, '$.area')[0]
        d = dateutil.parser.parse(jsonpath(self.heatpumpstate,
                                  '$.heatPumpConfig.changedTime')[0])
        self._current_temperature = jsonpath(
            self.heatpumpstate, '$.latestClimateSample.temperature')[0]

        if self._config_date is None or self._config_date < d:
            self._target_temperature = jsonpath(
                self.heatpumpstate, '$.heatPumpConfig.targetTemperature')[0]
            current_operation = jsonpath(
                self.heatpumpstate, '$.heatPumpConfig.mode')[0]
            self._current_operation = VERISIRE_HASS_OP_MODE[current_operation]
            self._current_fan_mode = jsonpath(
                self.heatpumpstate, '$.heatPumpConfig.fanSpeed')[0].title()
            self._current_swing_mode = jsonpath(
                self.heatpumpstate,
                '$.heatPumpConfig.airSwingDirection.vertical')[0].title()
            self._on = True if jsonpath(
                self.heatpumpstate,
                '$.heatPumpConfig.power')[0] == 'ON' else False
            self._config_date = d

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def target_temperature_step(self):
        return 1.0

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._on

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if self._on:
            if kwargs.get(ATTR_TEMPERATURE) is not None:
                self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
                hub.session.set_heat_pump_target_temperature(
                    self.id, self._target_temperature)
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new swing setting."""
        if self._on:
            hub.session.set_heat_pump_airswingdirection(
                self.id, swing_mode.upper())
            self._current_swing_mode = swing_mode
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        if self._on:
            hub.session.set_heat_pump_fan_speed(self.id, fan_mode.upper())
            self._current_fan_mode = fan_mode
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        if self._on:
            hub.session.set_heat_pump_mode(
                self.id, HASS_VERISURE_OP_MODE[operation_mode])
            self._current_operation = operation_mode
        self.schedule_update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_on(self):
        """Turn on."""
        hub.session.set_heat_pump_power(self.id, 'ON')
        self._on = True
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        hub.session.set_heat_pump_power(self.id, 'OFF')
        self._on = False
        self.schedule_update_ha_state()

    def update(self):
        self.sync_data()