"""Climate control on Zigbee Home Automation networks."""
import logging

from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_UNKNOWN, TEMP_CELSIUS)
from homeassistant.components.fan import (
    SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH)
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH,
    DOMAIN, SUPPORT_AUX_HEAT, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE, SUPPORT_FAN_MODE,
    HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL,
    HVAC_MODE_FAN_ONLY, HVAC_MODE_DRY, HVAC_MODE_OFF,
    CURRENT_HVAC_HEAT, CURRENT_HVAC_COOL, CURRENT_HVAC_FAN,
    CURRENT_HVAC_OFF)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, THERMOSTAT_CHANNEL,
    FAN_CHANNEL, SIGNAL_SET_FAN, SIGNAL_ATTR_UPDATED
)
from .sensor import temperature_formatter
from .entity import ZhaEntity
from .fan import SPEED_ON, SPEED_AUTO, SPEED_SMART, SEQUENCE_LIST

_LOGGER = logging.getLogger(__name__)

CTRLSEQ_COOLING_ONLY = 0
CTRLSEQ_COOLING_REHEAT = 1
CTRLSEQ_HEATING_ONLY = 2
CTRLSEQ_HEATING_REHEAT = 3
CTRLSEQ_COOLING_HEATING = 4
CTRLSEQ_COOLING_HEATING_REHEAT = 5

RUNNING_STATE_HEAT = 1
RUNNING_STATE_COOL = 2
RUNNING_STATE_FAN = 4
RUNNING_STATE_HEAT2 = 8
RUNNING_STATE_COOL2 = 16
RUNNING_STATE_FAN2 = 32
RUNNING_STATE_FAN3 = 64

SYSTEM_MODE_LIST = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT_COOL,
    STATE_UNKNOWN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
    HVAC_MODE_OFF
]

EMERGENCY_HEAT_MODE = 5

SPEED_LIST = [
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    SPEED_ON,
    SPEED_AUTO,
    SPEED_SMART
]

SPEED_TO_VALUE = {speed: i for i, speed in enumerate(SPEED_LIST)}

SUPPORT_FLAGS = SUPPORT_AUX_HEAT

TEMP_TO_VALUE = 100

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation thermostats."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation thermostat from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    thermostats = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if thermostats is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    thermostats.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA thermostats."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(ZhaThermostat(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class ZhaThermostat(ZhaEntity, ClimateDevice):
    """Representation of a ZHA thermostat."""

    _domain = DOMAIN

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""

        self._action = None
        self._fan_mode = None
        self._fan_speed_list = None
        self._local_temperature = None
        self._occupied_cooling_setpoint = None
        self._occupied_heating_setpoint = None
        self._min_cool_setpoint = None
        self._max_cool_setpoint = None
        self._min_heat_setpoint = None
        self._max_heat_setpoint = None
        self._operation_mode = HVAC_MODE_OFF
        self._available_actions = [HVAC_MODE_OFF]
        self._emergency_heat = None
        self._support_flags = SUPPORT_FLAGS

        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._thermostat_channel = self.cluster_channels.get(THERMOSTAT_CHANNEL)
        self._fan_channel = self.cluster_channels.get(FAN_CHANNEL)

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()

        if self._fan_channel:
            await self.async_accept_signal(
                self._fan_channel, SIGNAL_SET_FAN, self.async_set_fan_state)

            value = await self._fan_channel.get_attribute_value(
                'fan_mode_sequence')
            if value is not None and value < len(SEQUENCE_LIST):
                # Thermostat fans don't support off mode.
                self._fan_speed_list = SEQUENCE_LIST[value].copy()
                self._fan_speed_list.remove(SPEED_OFF)

            value = await self._fan_channel.get_attribute_value(
                'fan_mode_sequence')

            self._support_flags |= SUPPORT_FAN_MODE

        await self.async_accept_signal(
            self._thermostat_channel, SIGNAL_ATTR_UPDATED, self.async_set_therm_state)

        value = await self._thermostat_channel.get_attribute_value(
            'min_heat_setpoint_limit')
        self._min_heat_setpoint = temperature_formatter(value)
        value = await self._thermostat_channel.get_attribute_value(
            'max_heat_setpoint_limit')
        self._max_heat_setpoint = temperature_formatter(value)
        value = await self._thermostat_channel.get_attribute_value(
            'min_cool_setpoint_limit')
        self._min_cool_setpoint = temperature_formatter(value)
        value = await self._thermostat_channel.get_attribute_value(
            'max_cool_setpoint_limit')
        self._max_cool_setpoint = temperature_formatter(value)

        value = await self._thermostat_channel.get_attribute_value(
            'ctrl_seqe_of_oper')
        if value in (CTRLSEQ_COOLING_ONLY, CTRLSEQ_COOLING_REHEAT):
            self._available_actions = [HVAC_MODE_OFF, HVAC_MODE_COOL]
            self._support_flags |= SUPPORT_TARGET_TEMPERATURE
        elif value in (CTRLSEQ_HEATING_ONLY, CTRLSEQ_HEATING_REHEAT):
            self._available_actions = [HVAC_MODE_OFF, HVAC_MODE_HEAT]
            self._support_flags |= SUPPORT_TARGET_TEMPERATURE
        elif value in (CTRLSEQ_COOLING_HEATING, CTRLSEQ_COOLING_HEATING_REHEAT):
            self._available_actions = [HVAC_MODE_OFF, HVAC_MODE_HEAT,
                                       HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL]
            self._support_flags |= SUPPORT_TARGET_TEMPERATURE_RANGE

        self.async_schedule_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum setpoint temperature."""
        if (self._operation_mode == HVAC_MODE_COOL or
                HVAC_MODE_HEAT not in self._available_actions):
            if self._min_cool_setpoint:
                return self._min_cool_setpoint
            return super().min_temp

        if self._min_heat_setpoint:
            return self._min_heat_setpoint
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum setpoint temperature."""
        if (self._operation_mode == HVAC_MODE_HEAT or
                HVAC_MODE_COOL not in self._available_actions):
            if self._max_heat_setpoint:
                return self._max_heat_setpoint
            return super().max_temp

        if self._max_cool_setpoint:
            return self._max_cool_setpoint
        return super().max_temp

    @property
    def is_aux_heat(self):
        """Returns true if aux heater is on."""
        return self._emergency_heat

    @property
    def is_on(self):
        """Returns true if device is currently on."""
        if self._action is None:
            return None
        return self._action != CURRENT_HVAC_OFF

    @property
    def hvac_action(self):
        """Return the current state."""
        return self._action

    @property
    def hvac_mode(self):
        """Return the current operating mode."""
        return self._operation_mode

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._available_actions

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_speed_list

    @property
    def current_temperature(self):
        """Return the local temperature"""
        return self._local_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if HVAC_MODE_HEAT_COOL in self._available_actions:
            if self._operation_mode == HVAC_MODE_COOL:
                return self._occupied_cooling_setpoint
            return self._occupied_heating_setpoint

        if HVAC_MODE_COOL in self._available_actions:
            return self._occupied_cooling_setpoint
        return self._occupied_heating_setpoint

    @property
    def target_temperature_high(self):
        """Return the target temperature high."""
        return self._occupied_cooling_setpoint

    @property
    def target_temperature_low(self):
        """Return the target temperature low."""
        return self._occupied_heating_setpoint

    def async_set_fan_state(self, value):
        """Handle state update from fan channel."""
        if value < len(SPEED_LIST):
            self._fan_mode = SPEED_LIST[value]

        self.async_schedule_update_ha_state()

    def async_set_therm_state(self, name, value):
        """Handle state update from thermostat channel."""
        if name == 'local_temp':
            self._local_temperature = temperature_formatter(value)
        if name == 'occupied_cooling_setpoint':
            self._occupied_cooling_setpoint = temperature_formatter(value)
        if name == 'occupied_heating_setpoint':
            self._occupied_heating_setpoint = temperature_formatter(value)
        if name == 'system_mode':
            if value < len(SYSTEM_MODE_LIST):
                self._operation_mode = SYSTEM_MODE_LIST[value]
                self._emergency_heat = (value == EMERGENCY_HEAT_MODE)
        if name == 'running_state':
            self._get_running_state(value)

        self.async_schedule_update_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode"""
        if self._fan_channel:
            await self._fan_channel.async_set_speed(SPEED_LIST.index(fan_mode))

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        if hvac_mode not in SYSTEM_MODE_LIST:
            return

        if hvac_mode is HVAC_MODE_HEAT and self._emergency_heat is True:
            await self._thermostat_channel.async_set_system_mode(EMERGENCY_HEAT_MODE)

        await self._thermostat_channel.async_set_system_mode(SYSTEM_MODE_LIST.index(hvac_mode))

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        await self._thermostat_channel.async_set_system_mode(EMERGENCY_HEAT_MODE)

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        await self._thermostat_channel.async_set_system_mode(
            SYSTEM_MODE_LIST.index(HVAC_MODE_HEAT))

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if HVAC_MODE_HEAT_COOL in self._available_actions:
            low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
            high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if low_temp is not None:
                self._limit_temp(low_temp)
                await self._thermostat_channel.async_set_heating_setpoint(
                    low_temp * TEMP_TO_VALUE)
            if high_temp is not None:
                self._limit_temp(high_temp)
                await self._thermostat_channel.async_set_cooling_setpoint(
                    high_temp * TEMP_TO_VALUE)
        elif HVAC_MODE_COOL in self._available_actions:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            if temperature is not None:
                self._limit_temp(temperature)
                await self._thermostat_channel.async_set_cooling_setpoint(
                    temperature * TEMP_TO_VALUE)
        elif HVAC_MODE_HEAT in self._available_actions:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            if temperature is not None:
                self._limit_temp(temperature)
                await self._thermostat_channel.async_set_heating_setpoint(
                    temperature * TEMP_TO_VALUE)

    async def async_update(self):
        """Attempt to retrieve state from the fan and thermostat."""
        await super().async_update()

        if self._fan_channel:
            value = await self._fan_channel.get_attribute_value('fan_mode')
            if value is not None and value < len(SPEED_LIST):
                self._fan_mode = SPEED_LIST[value]

        if self._thermostat_channel:
            value = await self._thermostat_channel.get_attribute_value(
                'local_temp')
            if value is not None:
                self._local_temperature = temperature_formatter(value)

            value = await self._thermostat_channel.get_attribute_value(
                'occupied_cooling_setpoint')
            if value is not None:
                self._occupied_cooling_setpoint = temperature_formatter(value)

            value = await self._thermostat_channel.get_attribute_value(
                'occupied_heating_setpoint')
            if value is not None:
                self._occupied_heating_setpoint = temperature_formatter(value)

            value = await self._thermostat_channel.get_attribute_value(
                'system_mode')
            if value is not None and value < len(SYSTEM_MODE_LIST):
                self._operation_mode = SYSTEM_MODE_LIST[value]
                self._emergency_heat = (value == EMERGENCY_HEAT_MODE)

            value = await self._thermostat_channel.get_attribute_value(
                'running_state')
            if value is not None:
                self._get_running_state(value)


    def _get_running_state(self, value):
        if value & RUNNING_STATE_COOL or value & RUNNING_STATE_COOL2:
            self._action = CURRENT_HVAC_COOL
        elif value & RUNNING_STATE_HEAT or value & RUNNING_STATE_HEAT2:
            self._action = CURRENT_HVAC_HEAT
        elif (value & RUNNING_STATE_FAN or value & RUNNING_STATE_FAN2 or
              value & RUNNING_STATE_FAN3):
            self._action = CURRENT_HVAC_FAN
        else:
            self._action = CURRENT_HVAC_OFF

    def _limit_temp(self, temp):
        """Limit temperature between min and max."""
        if not self.min_temp or not self.max_temp:
            return
        if temp < self.min_temp:
            temp = self.min_temp
        elif temp > self.max_temp:
            temp = self.max_temp
