"""Support for Insteon Thermostats via ISY994 Platform."""
import logging
from typing import List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN, FAN_AUTO, FAN_ON,
    HVAC_MODE_COOL, HVAC_MODE_HEAT, SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_TEMPERATURE_RANGE)
from homeassistant.const import (
    ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from . import ISYDevice
from .const import (
    HA_FAN_TO_ISY, HA_HVAC_TO_ISY, ISY994_NODES, ISY_CURRENT_HUMIDITY,
    ISY_FAN_MODE, ISY_HVAC_MODE, ISY_HVAC_MODES, ISY_HVAC_STATE,
    ISY_TARGET_TEMP_HIGH, ISY_TARGET_TEMP_LOW, ISY_UOM, UOM_TO_STATES)

_LOGGER = logging.getLogger(__name__)

ISY_SUPPORTED_FEATURES = (SUPPORT_FAN_MODE |
                          SUPPORT_TARGET_TEMPERATURE |
                          SUPPORT_TARGET_TEMPERATURE_RANGE)


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
        self._uom = self._node.uom
        if isinstance(self._uom, list):
            self._uom = self._node.uom[0]
        self._hvac_action = None
        self._hvac_mode = None
        self._fan_mode = None
        self._temp_unit = None
        self._current_humidity = 0
        self._target_temp_low = 0
        self._target_temp_high = 0

    async def async_added_to_hass(self):
        """Delayed completion of initialization."""
        current_humidity = self._node.aux_properties.get(
            ISY_CURRENT_HUMIDITY)
        if current_humidity:
            self._current_humidity = int(current_humidity.get('value', 0))

        target_temp_high = self._node.aux_properties.get(ISY_TARGET_TEMP_HIGH)
        if target_temp_high:
            self._target_temp_high = \
                self.fix_temp(target_temp_high.get('value'))

        target_temp_low = self._node.aux_properties.get(ISY_TARGET_TEMP_LOW)
        if target_temp_low:
            self._target_temp_low = \
                self.fix_temp(target_temp_low.get('value'))

        hvac_mode = self._node.aux_properties.get(ISY_HVAC_MODE)
        if hvac_mode:
            self._hvac_mode = UOM_TO_STATES['98']. \
                get(str(hvac_mode.get('value')))

        self._node.controlEvents.subscribe(self._node_control_handler)
        await super().async_added_to_hass()

    def _node_control_handler(self, event: object) -> None:
        """Handle control events coming from the primary node.

        The ISY does not report some properties on the root of the node,
            they only show up in the event log:

        ISY_FAN_MODE, ISY_HVAC_STATE, ISY_UOM will be set the first
            time the event is fired by the ISY for those controls.

        Current Temperature is updated by PyISY in node.status and we don't
            need to listen for it here.
        """
        if event.event == ISY_FAN_MODE:
            self._fan_mode = UOM_TO_STATES['99'].get(str(event.nval))
        elif event.event == ISY_HVAC_STATE:
            self._hvac_action = UOM_TO_STATES['66'].get(str(event.nval))
        elif event.event == ISY_HVAC_MODE:
            self._hvac_mode = UOM_TO_STATES['98'].get(str(event.nval))
        elif event.event == ISY_UOM:
            if int(event.nval) == 1:
                self._temp_unit = TEMP_CELSIUS
            elif int(event.nval) == 2:
                self._temp_unit = TEMP_FAHRENHEIT
        elif event.event == ISY_CURRENT_HUMIDITY:
            self._current_humidity = int(event.nval)
        elif event.event == ISY_TARGET_TEMP_HIGH:
            self._target_temp_high = self.fix_temp(event.nval)
        elif event.event == ISY_TARGET_TEMP_LOW:
            self._target_temp_low = self.fix_temp(event.nval)
        self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ISY_SUPPORTED_FEATURES

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

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
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return ISY_HVAC_MODES

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        return self._hvac_action

    @property
    def value(self):
        """Get the current value of the device.

        Required to override the default ISYDevice method.
        """
        return self.fix_temp(self._node.status)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.value

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_COOL:
            return self._target_temp_high
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self._target_temp_low
        return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._target_temp_high

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._target_temp_low

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [FAN_AUTO, FAN_ON]

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode ie. auto, on."""
        return self._fan_mode

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp is not None:
            if self.hvac_mode == HVAC_MODE_COOL:
                target_temp_high = target_temp
            if self.hvac_mode == HVAC_MODE_HEAT:
                target_temp_low = target_temp
        if target_temp_low is not None:
            self._node.climate_setpoint_heat(int(target_temp_low))
            # Presumptive setting--event stream will correct if cmd fails:
            self._target_temp_low = target_temp_low
        if target_temp_high is not None:
            self._node.climate_setpoint_cool(int(target_temp_high))
            # Presumptive setting--event stream will correct if cmd fails:
            self._target_temp_high = target_temp_high
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.debug('Requested fan mode %s', fan_mode)
        self._node.fan_state(HA_FAN_TO_ISY.get(fan_mode))
        # Presumptive setting--event stream will correct if cmd fails:
        self._fan_mode = fan_mode
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug('Requested operation mode %s', hvac_mode)
        self._node.climate_mode(HA_HVAC_TO_ISY.get(hvac_mode))
        # Presumptive setting--event stream will correct if cmd fails:
        self._hvac_mode = hvac_mode
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
        if self._node.prec is not None and self._node.prec != '0':
            return round(float(temp) * pow(10, -int(self._node.prec)),
                         int(self._node.prec))
        return int(temp)
