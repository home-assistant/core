"""Support for Insteon Thermostats via ISY994 Platform."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    DOMAIN, STATE_AUTO, STATE_COOL, STATE_FAN_ONLY, STATE_HEAT, STATE_IDLE,
    SUPPORT_FAN_MODE, SUPPORT_HOLD_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    PRECISION_TENTHS, STATE_OFF, STATE_ON, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.util.temperature import convert as convert_temperature

from . import ISYDevice
from .const import (
    ISY994_NODES, ISY_CURRENT_HUMIDITY, ISY_FAN_MODE,
    ISY_OPERATION_MODE, ISY_OPERATION_STATE, ISY_TARGET_TEMP_HIGH,
    ISY_TARGET_TEMP_LOW, ISY_UOM, UOM_TO_STATES)

_LOGGER = logging.getLogger(__name__)


DEFAULT_MIN_TEMP = 10
DEFAULT_MAX_TEMP = 30

# Translate ISY Operation Mode to HASS States & Hold Modes
VALUE_TO_HASS_MODE = {
    0: (STATE_OFF, 'temp'),
    1: (STATE_HEAT, 'temp'),
    2: (STATE_COOL, 'temp'),
    3: (STATE_AUTO, 'temp'),
    4: (STATE_FAN_ONLY, 'temp'),
    5: (STATE_AUTO, 'program'),
    6: (STATE_HEAT, 'program'),
    7: (STATE_COOL, 'program')
}

ISY_OPERATION_LIST = [STATE_HEAT, STATE_COOL, STATE_AUTO,
                      STATE_FAN_ONLY, STATE_OFF]

ISY_SUPPORTED_MODES = (SUPPORT_OPERATION_MODE |
                       SUPPORT_FAN_MODE |
                       SUPPORT_HOLD_MODE |
                       SUPPORT_TARGET_TEMPERATURE_HIGH |
                       SUPPORT_TARGET_TEMPERATURE_LOW)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the ISY994 thermostat platform."""
    devices = []

    for node in hass.data[ISY994_NODES][DOMAIN]:
        _LOGGER.debug('Adding ISY node %s to Climate platform', node)
        devices.append(ISYThermostatDevice(node))

    async_add_entities(devices)


class ISYThermostatDevice(ISYDevice, ClimateDevice):
    """Representation of an ISY994 thermostat device."""

    def __init__(self, node) -> None:
        """Initialize the ISY Thermostat Device."""
        super().__init__(node)
        self._node = node
        self._uom = ''
        if len(self._node.uom) == 1:
            self._uom = self._node.uom[0]
        self._current_status = None
        self._current_hold_mode = None
        self._current_humidity = 0
        self._target_temp_low = 0
        self._target_temp_high = 0
        self._fan_mode = None
        self._current_operation = None
        self._current_isy_operation = None
        self._temp_unit = None

    async def async_added_to_hass(self):
        """Delayed completion of initialization."""
        current_humidity = next((i for i in self._node.aux_properties.values()
                                 if i['id'] == ISY_CURRENT_HUMIDITY), False)
        if current_humidity:
            self._current_humidity = current_humidity['value']

        target_temp_high = next((i for i in self._node.aux_properties.values()
                                 if i['id'] == ISY_TARGET_TEMP_HIGH), False)
        if target_temp_high:
            self._target_temp_high = self.fix_temp(target_temp_high['value'])

        target_temp_low = next((i for i in self._node.aux_properties.values()
                                if i['id'] == ISY_TARGET_TEMP_LOW), False)
        if target_temp_low:
            self._target_temp_low = self.fix_temp(target_temp_low['value'])

        current_operation = next((i for i in self._node.aux_properties.values()
                                  if i['id'] == ISY_OPERATION_MODE), False)
        if current_operation:
            self._current_isy_operation = UOM_TO_STATES['98'].get(
                str(current_operation['value']), None)
            self._current_operation, self._current_hold_mode = \
                VALUE_TO_HASS_MODE.get(current_operation['value'], None)

        self._node.controlEvents.subscribe(self._node_control_handler)
        await super().async_added_to_hass()

    def _node_control_handler(self, event: object) -> None:
        """Handle control events coming from the primary node.

        The ISY does not report some properties on the root of the node,
            they only show up in the event log:

        ISY_FAN_MODE, ISY_OPERATION_STATE, ISY_UOM will be set the first
            time the event is fired by the ISY for those controls.

        Current Temperature is updated by PyISY in node.status and we don't
            need to listen for it here.
        """
        if event.event == ISY_FAN_MODE:
            self._fan_mode = UOM_TO_STATES['99'].get(event.nval, None)
        elif event.event == ISY_OPERATION_STATE:
            self._current_status = UOM_TO_STATES['66'].get(event.nval, None)
        elif event.event == ISY_OPERATION_MODE:
            self._current_isy_operation = \
                UOM_TO_STATES['98'].get(event.nval, None)
            self._current_operation, self._current_hold_mode = \
                VALUE_TO_HASS_MODE.get(int(event.nval), None)
        elif event.event == ISY_UOM:
            if int(event.nval) == 1:
                self._temp_unit = TEMP_CELSIUS
            elif int(event.nval) == 2:
                self._temp_unit = TEMP_FAHRENHEIT
        elif event.event == ISY_CURRENT_HUMIDITY:
            self._current_humidity = int(event.nval)
        elif event.event == ISY_TARGET_TEMP_HIGH:
            self._target_temp_high = self.fix_temp(int(event.nval))
        elif event.event == ISY_TARGET_TEMP_LOW:
            self._target_temp_low = self.fix_temp(int(event.nval))
        self.schedule_update_ha_state()

    @property
    def state(self):
        """Return the current state."""
        return self._current_status

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def value(self):
        """Get the current value of the device."""
        return self.fix_temp(self._node.status)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._temp_unit:
            return self._temp_unit
        return self.hass.config.units.temperature_unit

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def current_operation(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return ISY_OPERATION_LIST

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.value

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._target_temp_high

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._target_temp_low

    @property
    def current_hold_mode(self):
        """Return the current hold mode, e.g., home, away, temp."""
        return self._current_hold_mode

    @property
    def is_on(self):
        """Return if the unit is on or off based on operation status."""
        if self._current_status not in [STATE_OFF, STATE_IDLE, None]:
            return True
        return False

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return [STATE_AUTO, STATE_ON]

    @property
    def current_fan_mode(self) -> str:
        """Return the current fan mode ie. auto, on."""
        return self._fan_mode

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ISY_SUPPORTED_MODES

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(DEFAULT_MIN_TEMP, TEMP_CELSIUS,
                                   self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(DEFAULT_MAX_TEMP, TEMP_CELSIUS,
                                   self.temperature_unit)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if 'target_temp_high' in kwargs and kwargs['target_temp_high'] != \
                self._target_temp_high:
            self._node.climate_setpoint_cool(int(kwargs['target_temp_high']))
            self._target_temp_high = kwargs['target_temp_high']
        if 'target_temp_low' in kwargs and kwargs['target_temp_low'] != \
                self._target_temp_low:
            self._node.climate_setpoint_heat(int(kwargs['target_temp_low']))
            self._target_temp_low = kwargs['target_temp_low']
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.debug('Requested fan mode %s', fan_mode)
        self._node.fan_by_mode(fan_mode)
        self._fan_mode = fan_mode
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        _LOGGER.debug('Requested operation mode %s', operation_mode)
        if operation_mode in [STATE_AUTO, STATE_COOL, STATE_HEAT] and \
                self._current_hold_mode == 'program':
            self._current_hold_mode = 'temp'
        self._node.climate_by_mode(operation_mode)
        self._current_operation = operation_mode
        self.schedule_update_ha_state()

    def set_hold_mode(self, hold_mode):
        """Set new target hold mode."""
        _LOGGER.debug('Requested hold mode %s', hold_mode)
        if hold_mode == 'program' and self._current_hold_mode != 'program':
            self._node.climate_by_mode('program_auto')
            self._current_operation = STATE_AUTO
        elif hold_mode == 'temp' and self._current_hold_mode != 'temp':
            self._node.climate_by_mode(self._current_operation)
        self._current_hold_mode = hold_mode
        self.schedule_update_ha_state()

    def fix_temp(self, temp) -> float:
        """Fix Insteon Thermostats' Reported Temperature.

        Insteon Thermostats report temperature in 0.5-deg precision as an int
        by sending a value of 2 times the Temp. Correct by dividing by 2 here.
        """
        if temp is None or temp == -1 * float('inf'):
            return None
        if self._uom == '101' or self._uom == 'degrees':
            return round(int(temp) / 2.0, 1)
        return round(int(temp) / 10, 1)
