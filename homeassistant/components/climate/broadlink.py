"""
Support for Chinese wifi thermostats (Floureon, Beok, Beca Energy)
configuration.yaml
climate:
  - platform: broadlink
    name: xxx
    mac: xxxx
    host: xxxx
"""
import logging
import json

import voluptuous as vol

from homeassistant.components.climate import (
    STATE_AUTO, ClimateDevice,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, PLATFORM_SCHEMA, STATE_MANUAL, STATE_IDLE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE,
    CONF_NAME, CONF_HOST, CONF_MAC)
import homeassistant.helpers.config_validation as cv
from socket import timeout

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'broadlink'
REQUIREMENTS = ['broadlink==0.9.0']

DEFAULT_NAME = 'broadlink'

POWER_ON = 1
POWER_OFF = 0
AUTO = 1
MANUAL = 0
CONF_MODE_LIST = 'modes'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
CONF_ADVANCED_CONFIG = 'advanced_config'
CONF_SCHEDULE_WEEKDAY = 'schedule_week_day'
CONF_SCHEDULE_WEEKEND = 'schedule_week_end'
CONF_WEEKDAY = "weekday"
CONF_WEEKEND = "weekend"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_MIN_TEMP, default=5): cv.positive_int,
    vol.Optional(CONF_MAX_TEMP, default=35): cv.positive_int,
    vol.Optional(CONF_ADVANCED_CONFIG,
                 default='{"loop_mode": "0", '
                         '"sen": "0", '
                         '"osv": "42", '
                         '"dif": "2", '
                         '"svh": "35", '
                         '"svl": "5", '
                         '"adj": "0", '
                         '"fre": "01", '
                         '"pon": "00"}'): cv.string,
    vol.Optional(CONF_SCHEDULE_WEEKDAY,
                 default='[{"start_hour":"06", '
                         '"start_minute":"30", '
                         '"temp":"20"}, '
                         '{"start_hour":"09", '
                         '"start_minute":"00", '
                         '"temp":"17"}, '
                         '{"start_hour":"12", '
                         '"start_minute":"00", '
                         '"temp":"20" }, '
                         '{"start_hour":"14", '
                         '"start_minute":"00", '
                         '"temp":"17"}, '
                         '{"start_hour":"18", '
                         '"start_minute":"00", '
                         '"temp":"20" }, '
                         '{"start_hour":22, '
                         '"start_minute":30, '
                         '"temp":17}]'): cv.string,
    vol.Optional(CONF_SCHEDULE_WEEKEND,
                 default='[{"start_hour":"08", '
                         '"start_minute":"30", '
                         '"temp":"20"}, '
                         '{"start_hour":"23", '
                         '"start_minute":"00", '
                         '"temp":"17"}]'): cv.string
})

SET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required(CONF_WEEKDAY,
                 default='[{'
                         '"start_hour":"06", '
                         '"start_minute":"30", '
                         '"temp":"20"}, '
                         '{"start_hour":"09", '
                         '"start_minute":"00", '
                         '"temp":"17"}, '
                         '{"start_hour":"12", '
                         '"start_minute":"00", '
                         '"temp":"20" }, '
                         '{"start_hour":"14", '
                         '"start_minute":"00", '
                         '"temp":"17"}, '
                         '{"start_hour":"18", '
                         '"start_minute":"00", '
                         '"temp":"20" }, '
                         '{"start_hour":22, '
                         '"start_minute":30, '
                         '"temp":17}]'): cv.string,
    vol.Required(CONF_WEEKEND,
                 default='[{"start_hour":"08", '
                         '"start_minute":"30", '
                         '"temp":"20"}, '
                         '{"start_hour":"23", '
                         '"start_minute":"00", '
                         '"temp":"17"}]'): cv.string
})

SET_ADVANCED_CONF_SCHEMA = vol.Schema({
    vol.Required(CONF_ADVANCED_CONFIG,
                 default='{"loop_mode": "0", '
                         '"sen": "0", '
                         '"osv": "42", '
                         '"dif": "2", '
                         '"svh": "35", '
                         '"svl": "5", '
                         '"adj": "0", '
                         '"fre": "01", '
                         '"pon": "00"}'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the broadlink thermostat platform."""
    _LOGGER.debug("Adding component: wifi_thermostat ...")

    mac_addr = config.get(CONF_MAC)
    ip_addr = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    if mac_addr is None:
        _LOGGER.error("Wifi Thermostat: Invalid mac_addr !")
        return False

    if ip_addr is None:
        _LOGGER.error("Wifi Thermostat: Invalid ip_addr !")
        return False

    if name is None:
        _LOGGER.error("Wifi Thermostat: Invalid name !")
        return False

    wifi_thermostat = WifiThermostat(mac_addr,
                        ip_addr,
                        name,
                        config.get(CONF_ADVANCED_CONFIG),
                        config.get(CONF_SCHEDULE_WEEKDAY),
                        config.get(CONF_SCHEDULE_WEEKDAY),
                        config.get(CONF_MIN_TEMP),
                        config.get(CONF_MAX_TEMP))

    add_devices([BroadlinkThermostat(wifi_thermostat)], True)

    def handle_set_schedule(service):
        """Handle data for the set_schedule service call."""
        thermostat = WifiThermostat(config.get(CONF_MAC),
                                    config.get(CONF_HOST),
                                    config.get(CONF_NAME),
                                    config.get(CONF_ADVANCED_CONFIG),
                                    config.get(CONF_SCHEDULE_WEEKDAY),
                                    config.get(CONF_SCHEDULE_WEEKDAY),
                                    config.get(CONF_MIN_TEMP),
                                    config.get(CONF_MAX_TEMP))
        schedule_wd = service.data.get(CONF_SCHEDULE_WEEKDAY)
        schedule_we = service.data.get(CONF_SCHEDULE_WEEKEND)
        thermostat.set_schedule(
            {CONF_WEEKDAY:
             json.loads(schedule_wd.replace("'", '"'), cls=Decoder),
             CONF_WEEKEND:
             json.loads(schedule_we.replace("'", '"'), cls=Decoder)})

    #hass.services.register(DOMAIN, 'set_schedule', handle_set_schedule, schema=SET_SCHEDULE_SCHEMA)

    def handle_set_advanced_conf(service):
        """Handle data for the set_advanced_conf service call."""
        thermostat = WifiThermostat(config.get(CONF_MAC),
                                    config.get(CONF_HOST),
                                    config.get(CONF_NAME),
                                    config.get(CONF_ADVANCED_CONFIG),
                                    config.get(CONF_SCHEDULE_WEEKDAY),
                                    config.get(CONF_SCHEDULE_WEEKDAY),
                                    config.get(CONF_MIN_TEMP),
                                    config.get(CONF_MAX_TEMP))
        advanced_conf = service.data.get(CONF_ADVANCED_CONFIG)
        thermostat.set_advanced_config(
            json.loads(advanced_conf.replace("'", '"'), cls=Decoder))

    #hass.services.register(DOMAIN, 'set_advanced_conf', handle_set_advanced_conf, schema=SET_ADVANCED_CONF_SCHEMA)

    _LOGGER.debug("Wifi Thermostat: Component successfully added !")


class Decoder(json.JSONDecoder):
    import re

    FLAGS = re.VERBOSE | re.MULTILINE | re.DOTALL
    WHITESPACE = re.compile(r'[ \t\n\r]*', FLAGS)

    def decode(self, s, _w=WHITESPACE.match):
        result = super(Decoder, self).decode(s)
        return self._decode(result)

    def _decode(self, o):
        if isinstance(o, str):
            try:
                return int(o)
            except ValueError:
                try:
                    return float(o)
                except ValueError:
                    return o
        elif isinstance(o, dict):
            return {k: self._decode(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [self._decode(v) for v in o]
        else:
            return o


class WifiThermostat:
    def __init__(self, mac, ip, name, advanced_config,
                 schedule_wd, schedule_we, min_temp, max_temp):
        self.HOST = ip
        self.PORT = 80
        self.MAC = bytes.fromhex(''.join(reversed(mac.split(':'))))
        self.current_temp = None
        self.current_operation = None
        self.power = None
        self.target_temperature = None
        self.name = name
        self.loop_mode = json.loads(advanced_config, cls=Decoder)["loop_mode"]
        self.operation_list = [STATE_AUTO, STATE_IDLE, STATE_MANUAL]
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.state = 0
        self.freeze = 0
        self.advanced_config = json.loads(advanced_config, cls=Decoder)
        self.schedule = {CONF_WEEKDAY: json.loads(schedule_wd, cls=Decoder),
                         CONF_WEEKEND: json.loads(schedule_we, cls=Decoder)}
        self.set_advanced_config(self.advanced_config)
        self.set_schedule(self.schedule)

    def set_advanced_config(self, advanced_config):
        """Set the thermostat advanced config"""
        try:
            device = self.connect()
            if device.auth():
                device.set_advanced(advanced_config["loop_mode"],
                                    advanced_config["sen"],
                                    advanced_config["osv"],
                                    advanced_config["dif"],
                                    advanced_config["svh"],
                                    advanced_config["svl"],
                                    advanced_config["adj"],
                                    advanced_config["fre"],
                                    advanced_config["pon"])
        except timeout:
            _LOGGER.error("set_advanced_config timeout")

    def set_schedule(self, schedule):
        """Set the thermostat schedule"""
        try:
            device = self.connect()
            if device.auth():
                device.set_schedule(schedule[CONF_WEEKDAY],
                                    schedule[CONF_WEEKEND])
        except timeout:
            _LOGGER.error("set_schedule timeout")

    def power_on_off(self, power):
        """power on/off thermostat"""
        try:
            device = self.connect()
            if device.auth():
                if str(power) == STATE_IDLE:
                    device.set_power(POWER_OFF)
                else:
                    device.set_power(POWER_ON)
        except timeout:
            _LOGGER.error("power_on_off timeout")

    def set_temperature(self, temperature):
        """Set the thermostat target temperature"""
        try:
            device = self.connect()
            if device.auth():
                device.set_temp(float(temperature))
        except timeout:
            _LOGGER.error("set_temperature timeout")

    def set_operation_mode(self, mode):
        """Set the thermostat operation mode: [on, off, auto]"""
        try:
            device = self.connect()
            if device.auth():
                if mode == STATE_AUTO:
                    device.set_power(POWER_ON)
                    device.set_mode(AUTO, self.loop_mode)
                elif mode == STATE_MANUAL:
                    device.set_power(POWER_ON)
                    device.set_mode(MANUAL, self.loop_mode)
                elif mode == STATE_IDLE:
                    device.set_mode(MANUAL, self.loop_mode)
                    if self.freeze == 1:
                        device.set_temp(float(12))
                    else :
                        device.set_temp(float(0))
                    device.set_power(POWER_OFF)
        except timeout:
            _LOGGER.error("set_operation_mode timeout")

    def read_status(self):
        """Read thermostat data"""
        _LOGGER.debug("read_status")
        try:
            device = self.connect()
            if device.auth():
                data = device.get_full_status()
                json_data = json.loads(json.dumps(data))
                self.current_temp = json_data['room_temp']
                self.target_temperature = json_data['thermostat_temp']
                self.current_operation = STATE_IDLE \
                    if \
                    json_data["power"] == 0 \
                    else \
                    (STATE_AUTO
                     if
                     json_data["auto_mode"] == 1
                     else
                     STATE_MANUAL)
                self.state = STATE_MANUAL if json_data["active"] == 0 \
                    else STATE_IDLE
                self.freeze = data['fre']
        except timeout:
            _LOGGER.error("read_status timeout")

    def connect(self):
        """Open a connexion"""
        import broadlink
        return broadlink.gendevice(0x4EAD,
                                   (self.HOST,
                                    self.PORT),
                                   self.MAC)


class BroadlinkThermostat(ClimateDevice):
    """Representation of a Broadlink Thermostat device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._device.current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._device.max_temp

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._device.min_temp

    @property
    def current_operation(self):
        """Return current operation."""
        return self._device.current_operation

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._device.operation_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_temperature(kwargs.get(ATTR_TEMPERATURE))
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._device.set_operation_mode(operation_mode)
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn heater toggleable device on."""
        self._device.power_on_off(STATE_MANUAL)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn heater toggleable device off."""
        self._device.power_on_off(STATE_IDLE)
        self.schedule_update_ha_state()

    def set_advance_config(self, config_json):
        """Set the thermostat advanced config"""
        self._device.set_advanced_config(json.loads(config_json, cls=Decoder))
        self.schedule_update_ha_state()

    def set_schedule(self, schedule_json):
        """Set the thermostat schedule"""
        self._device.set_schedule(json.loads(schedule_json, cls=Decoder))
        self.schedule_update_ha_state()

    def update(self):
        """Update component data"""
        self._device.read_status()
