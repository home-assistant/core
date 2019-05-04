"""Support for the PRT Heatmiser themostats using the V3 protocol."""
import logging
import time
import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    STATE_HEAT, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_PORT, CONF_NAME, CONF_ID,
    PRECISION_WHOLE, STATE_OFF, STATE_ON, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_IPADDRESS = 'ipaddress'
CONF_TSTATS = 'tstats'
CONF_MODEL = 'model'
CONF_SENSOR = 'sensor'

TSTAT_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_MODEL): cv.string,
    vol.Required(CONF_SENSOR): cv.string,
})

TSTATS_SCHEMA = vol.All(cv.ensure_list, [TSTAT_SCHEMA])

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IPADDRESS): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Optional(CONF_TSTATS, default=[]): TSTATS_SCHEMA,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the heatmiser thermostat."""
    
    
    from heatmiserV3 import heatmiser, connection

    ipaddress = config.get(CONF_IPADDRESS)
    port = str(config.get(CONF_PORT))
    tstats = config.get(CONF_TSTATS)
    def_min_temp = 5
    def_max_temp = 35
    index = 0

    uh1 = connection.HeatmiserUH1(ipaddress, port)

    for tstat in tstats:
        index += 1
        room = tstat.get(CONF_ID)
        therm_id = tstat.get(CONF_ID)
        model = tstat.get(CONF_MODEL)
        sensor = tstat.get(CONF_SENSOR)
        thermostat = heatmiser.HeatmiserThermostat(therm_id, model, uh1)
        uh1_per = None
        if index == 1:
            uh1_per = uh1

        add_entities([
            HeatmiserV3Thermostat(
                thermostat, room, sensor, uh1_per,
                def_min_temp, def_max_temp)
                ])
        time.sleep(2.4)

        
class HeatmiserV3Thermostat(ClimateDevice):
    """Representation of a HeatmiserV3 thermostat."""

    
    def __init__(
                self, thermostat, name, sensor, uh1,
                def_min_temp, def_max_temp
                ):
        """Initialize the thermostat."""
        self.uh1 = uh1
        self.thermostat = thermostat
        self.statsensor = sensor
        self.dcb = None
        self.heating = 0
        self._current_temperature = 0
        self._target_temperature = 0
        self._name = name
        self._min_temp = def_min_temp
        self._max_temp = def_max_temp
        self._mode = STATE_UNKNOWN

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_WHOLE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [STATE_OFF, STATE_ON]

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._mode in [STATE_HEAT, STATE_OFF, STATE_ON, STATE_UNKNOWN]:
            return self._mode
        return None

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if self.heating == 0:
            self._min_temp = 7
            self._max_temp = 17
            self.heating = 1
            self._mode = STATE_OFF
        else:
            self._min_temp = 5
            self._max_temp = 35
            self.heating = 0
            self._mode = STATE_ON

        self.thermostat._hm_send_address(
            self.thermostat.address, 23, self.heating, 1)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.dcb is None:
            return 0
        if self.statsensor == 'floor':
            return self.themostat.get_floor_temp()
        return self.dcb[33]['value'] / 10

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.dcb is None:
            return 0
        if self.heating == 0:
            return self.thermostat.get_target_temp()
        return self.thermostat.get_frost_temp()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None or self.dcb is None:
            return
        if self.heating == 0:
            self.thermostat.set_target_temp(int(temperature))
            self._mode = STATE_ON
            if self._current_temperature < int(temperature):
                self._mode = STATE_HEAT
        else:
            self.thermostat.set_frost_protect_temp(int(temperature))
            self._mode = STATE_OFF
            if self._current_temperature < int(temperature):
                self._mode = STATE_HEAT

    def update(self):
        """Get the latest data."""
        self.dcb = self.thermostat.read_dcb()
        self.heating = self.dcb[23]['value']
        self._current_temperature = self.current_temperature
        self._target_temperature = self.target_temperature
        self._min_temp = 5
        self._max_temp = 35

        if self.heating == 0:
            self._mode = STATE_ON
            if self._current_temperature < self._target_temperature:
                self._mode = STATE_HEAT
        else:
            self._min_temp = 7
            self._max_temp = 17
            self._mode = STATE_OFF
            if self._current_temperature < self._target_temperature:
                self._mode = STATE_HEAT
