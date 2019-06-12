"""Support for climate devices through the SmartThings cloud API."""
import asyncio
import logging
from typing import Iterable, Optional, Sequence

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN, ClimateDevice)
from homeassistant.components.climate.const import (
    ATTR_OPERATION_MODE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    STATE_AUTO, STATE_COOL, STATE_DRY, STATE_ECO, STATE_FAN_ONLY, STATE_HEAT,
    SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_TEMPERATURE_HIGH,
    SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, TEMP_CELSIUS, TEMP_FAHRENHEIT)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

ATTR_OPERATION_STATE = 'operation_state'
MODE_TO_STATE = {
    'auto': STATE_AUTO,
    'cool': STATE_COOL,
    'eco': STATE_ECO,
    'rush hour': STATE_ECO,
    'emergency heat': STATE_HEAT,
    'heat': STATE_HEAT,
    'off': STATE_OFF
}
STATE_TO_MODE = {
    STATE_AUTO: 'auto',
    STATE_COOL: 'cool',
    STATE_ECO: 'eco',
    STATE_HEAT: 'heat',
    STATE_OFF: 'off'
}

AC_MODE_TO_STATE = {
    'auto': STATE_AUTO,
    'cool': STATE_COOL,
    'dry': STATE_DRY,
    'coolClean': STATE_COOL,
    'dryClean': STATE_DRY,
    'heat': STATE_HEAT,
    'heatClean': STATE_HEAT,
    'fanOnly': STATE_FAN_ONLY
}
STATE_TO_AC_MODE = {
    STATE_AUTO: 'auto',
    STATE_COOL: 'cool',
    STATE_DRY: 'dry',
    STATE_HEAT: 'heat',
    STATE_FAN_ONLY: 'fanOnly'
}

UNIT_MAP = {
    'C': TEMP_CELSIUS,
    'F': TEMP_FAHRENHEIT
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add climate entities for a config entry."""
    from pysmartthings import Capability

    ac_capabilities = [
        Capability.air_conditioner_mode,
        Capability.air_conditioner_fan_mode,
        Capability.switch,
        Capability.temperature_measurement,
        Capability.thermostat_cooling_setpoint]

    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    entities = []
    for device in broker.devices.values():
        if not broker.any_assigned(device.device_id, CLIMATE_DOMAIN):
            continue
        if all(capability in device.capabilities
               for capability in ac_capabilities):
            entities.append(SmartThingsAirConditioner(device))
        else:
            entities.append(SmartThingsThermostat(device))
    async_add_entities(entities, True)


def get_capabilities(capabilities: Sequence[str]) -> Optional[Sequence[str]]:
    """Return all capabilities supported if minimum required are present."""
    from pysmartthings import Capability

    supported = [
        Capability.air_conditioner_mode,
        Capability.demand_response_load_control,
        Capability.air_conditioner_fan_mode,
        Capability.power_consumption_report,
        Capability.relative_humidity_measurement,
        Capability.switch,
        Capability.temperature_measurement,
        Capability.thermostat,
        Capability.thermostat_cooling_setpoint,
        Capability.thermostat_fan_mode,
        Capability.thermostat_heating_setpoint,
        Capability.thermostat_mode,
        Capability.thermostat_operating_state]
    # Can have this legacy/deprecated capability
    if Capability.thermostat in capabilities:
        return supported
    # Or must have all of these thermostat capabilities
    thermostat_capabilities = [
        Capability.temperature_measurement,
        Capability.thermostat_cooling_setpoint,
        Capability.thermostat_heating_setpoint,
        Capability.thermostat_mode]
    if all(capability in capabilities
           for capability in thermostat_capabilities):
        return supported
    # Or must have all of these A/C capabilities
    ac_capabilities = [
        Capability.air_conditioner_mode,
        Capability.air_conditioner_fan_mode,
        Capability.switch,
        Capability.temperature_measurement,
        Capability.thermostat_cooling_setpoint]
    if all(capability in capabilities
           for capability in ac_capabilities):
        return supported
    return None


class SmartThingsThermostat(SmartThingsEntity, ClimateDevice):
    """Define a SmartThings climate entities."""

    def __init__(self, device):
        """Init the class."""
        super().__init__(device)
        self._supported_features = self._determine_features()
        self._current_operation = None
        self._operations = None

    def _determine_features(self):
        from pysmartthings import Capability

        flags = SUPPORT_OPERATION_MODE \
            | SUPPORT_TARGET_TEMPERATURE \
            | SUPPORT_TARGET_TEMPERATURE_LOW \
            | SUPPORT_TARGET_TEMPERATURE_HIGH
        if self._device.get_capability(
                Capability.thermostat_fan_mode, Capability.thermostat):
            flags |= SUPPORT_FAN_MODE
        return flags

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self._device.set_thermostat_fan_mode(fan_mode, set_status=True)

        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        mode = STATE_TO_MODE[operation_mode]
        await self._device.set_thermostat_mode(mode, set_status=True)

        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_set_temperature(self, **kwargs):
        """Set new operation mode and target temperatures."""
        # Operation state
        operation_state = kwargs.get(ATTR_OPERATION_MODE)
        if operation_state:
            mode = STATE_TO_MODE[operation_state]
            await self._device.set_thermostat_mode(mode, set_status=True)
            await self.async_update()

        # Heat/cool setpoint
        heating_setpoint = None
        cooling_setpoint = None
        if self.current_operation == STATE_HEAT:
            heating_setpoint = kwargs.get(ATTR_TEMPERATURE)
        elif self.current_operation == STATE_COOL:
            cooling_setpoint = kwargs.get(ATTR_TEMPERATURE)
        else:
            heating_setpoint = kwargs.get(ATTR_TARGET_TEMP_LOW)
            cooling_setpoint = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        tasks = []
        if heating_setpoint is not None:
            tasks.append(self._device.set_heating_setpoint(
                round(heating_setpoint, 3), set_status=True))
        if cooling_setpoint is not None:
            tasks.append(self._device.set_cooling_setpoint(
                round(cooling_setpoint, 3), set_status=True))
        await asyncio.gather(*tasks)

        # State is set optimistically in the commands above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update the attributes of the climate device."""
        thermostat_mode = self._device.status.thermostat_mode
        self._current_operation = MODE_TO_STATE.get(thermostat_mode)
        if self._current_operation is None:
            _LOGGER.debug('Device %s (%s) returned an invalid'
                          'thermostat mode: %s', self._device.label,
                          self._device.device_id, thermostat_mode)

        supported_modes = self._device.status.supported_thermostat_modes
        if isinstance(supported_modes, Iterable):
            operations = set()
            for mode in supported_modes:
                state = MODE_TO_STATE.get(mode)
                if state is not None:
                    operations.add(state)
                else:
                    _LOGGER.debug('Device %s (%s) returned an invalid '
                                  'supported thermostat mode: %s',
                                  self._device.label, self._device.device_id,
                                  mode)
            self._operations = operations
        else:
            _LOGGER.debug('Device %s (%s) returned invalid supported '
                          'thermostat modes: %s', self._device.label,
                          self._device.device_id, supported_modes)

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._device.status.thermostat_fan_mode

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._device.status.humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.status.temperature

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_OPERATION_STATE:
                self._device.status.thermostat_operating_state
        }

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._device.status.supported_thermostat_fan_modes

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operations

    @property
    def supported_features(self):
        """Return the supported features."""
        return self._supported_features

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.current_operation == STATE_COOL:
            return self._device.status.cooling_setpoint
        if self.current_operation == STATE_HEAT:
            return self._device.status.heating_setpoint
        return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return self._device.status.cooling_setpoint
        return None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return self._device.status.heating_setpoint
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        from pysmartthings import Attribute
        return UNIT_MAP.get(
            self._device.status.attributes[Attribute.temperature].unit)


class SmartThingsAirConditioner(SmartThingsEntity, ClimateDevice):
    """Define a SmartThings Air Conditioner."""

    def __init__(self, device):
        """Init the class."""
        super().__init__(device)
        self._operations = None

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self._device.set_fan_mode(fan_mode, set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        await self._device.set_air_conditioner_mode(
            STATE_TO_AC_MODE[operation_mode], set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        tasks = []
        # operation mode
        operation_mode = kwargs.get(ATTR_OPERATION_MODE)
        if operation_mode:
            tasks.append(self.async_set_operation_mode(operation_mode))
        # temperature
        tasks.append(self._device.set_cooling_setpoint(
            kwargs[ATTR_TEMPERATURE], set_status=True))
        await asyncio.gather(*tasks)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_turn_on(self):
        """Turn device on."""
        await self._device.switch_on(set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_turn_off(self):
        """Turn device off."""
        await self._device.switch_off(set_status=True)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Update the calculated fields of the AC."""
        operations = set()
        for mode in self._device.status.supported_ac_modes:
            state = AC_MODE_TO_STATE.get(mode)
            if state is not None:
                operations.add(state)
            else:
                _LOGGER.debug('Device %s (%s) returned an invalid supported '
                              'AC mode: %s', self._device.label,
                              self._device.device_id, mode)
        self._operations = operations

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._device.status.fan_mode

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return AC_MODE_TO_STATE.get(self._device.status.air_conditioner_mode)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.status.temperature

    @property
    def device_state_attributes(self):
        """
        Return device specific state attributes.

        Include attributes from the Demand Response Load Control (drlc)
        and Power Consumption capabilities.
        """
        attributes = [
            'drlc_status_duration',
            'drlc_status_level',
            'drlc_status_start',
            'drlc_status_override',
            'power_consumption_start',
            'power_consumption_power',
            'power_consumption_energy',
            'power_consumption_end'
        ]
        state_attributes = {}
        for attribute in attributes:
            value = getattr(self._device.status, attribute)
            if value is not None:
                state_attributes[attribute] = value
        return state_attributes

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._device.status.supported_ac_fan_modes

    @property
    def is_on(self):
        """Return true if on."""
        return self._device.status.switch

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operations

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_OPERATION_MODE | SUPPORT_TARGET_TEMPERATURE \
            | SUPPORT_FAN_MODE | SUPPORT_ON_OFF

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.status.cooling_setpoint

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        from pysmartthings import Attribute
        return UNIT_MAP.get(
            self._device.status.attributes[Attribute.temperature].unit)
