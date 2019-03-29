"""
Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""
from datetime import timedelta
import logging
from random import randint
import time
from typing import Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_OPERATION_MODE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN,
    STATE_AUTO, STATE_COOL, STATE_DRY, STATE_FAN_ONLY, STATE_HEAT, STATE_IDLE,
    SUPPORT_AWAY_MODE, SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_TEMPERATURE, PRECISION_HALVES, STATE_OFF, TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    async_call_later, async_track_time_interval)
from homeassistant.helpers.temperature import convert_temperature

from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, SIGNAL_ATTR_UPDATED, THERMOSTAT_CHANNEL,
    ZHA_DISCOVERY_NEW)
from .entity import ZhaEntity

DEPENDENCIES = ['zha']

ATTR_SYS_MODE = 'system_mode'
ATTR_RUNNING_MODE = 'running_mode'
ATTR_SETPT_CHANGE_SRC = 'setpoint_change_source'
ATTR_SETPT_CHANGE_AMT = 'setpoint_change_amount'
ATTR_OCCUPANCY = 'occupancy'
ATTR_OCCP_COOL_SETPT = 'occupied_cooling_setpoint'
ATTR_OCCP_HEAT_SETPT = 'occupied_heating_setpoint'
ATTR_UNACCP_HEAT_SETPT = 'unoccupied_heating_setpoint'
ATTR_UNACCP_COOL_SETPT = 'unoccupied_cooling_setpoint'


RUNNING_MODE = {
    0x00: STATE_OFF,
    0x03: STATE_COOL,
    0x04: STATE_HEAT,
}

SEQ_OF_OPERATION = {
    0x00: [STATE_OFF, STATE_COOL],  # cooling only
    0x01: [STATE_OFF, STATE_COOL],  # cooling with reheat
    0x02: [STATE_OFF, STATE_HEAT],  # heating only
    0x03: [STATE_OFF, STATE_HEAT],  # heating with reheat
    # cooling and heating 4-pipes
    0x04: [STATE_OFF, STATE_AUTO, STATE_COOL, STATE_HEAT],
    # cooling and heating 4-pipes
    0x05: [STATE_OFF, STATE_AUTO, STATE_COOL, STATE_HEAT],
}

STATE_2_SYSTEM_MODE = {
    STATE_OFF: 0x00,
    STATE_AUTO: 0x01,
    STATE_COOL: 0x03,
    STATE_HEAT: 0x04,
    STATE_FAN_ONLY: 0x07,
    STATE_DRY: 0x08,
    STATE_IDLE: 0x09,
}

SYSTEM_MODE = {
    0x00: STATE_OFF,
    0x01: STATE_AUTO,
    0x03: STATE_COOL,
    0x04: STATE_HEAT,
    0x05: 'Emergency heating',
    0x06: STATE_COOL,  # this is 'precooling'. is it the same?
    0x07: STATE_FAN_ONLY,
    0x08: STATE_DRY,
    0x09: STATE_IDLE,
}

ZCL_TEMP = 100
SECS_2000_01_01 = 946702800

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation sensor from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    climate_entities = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if climate_entities is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    climate_entities.values())
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA sensors."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(await get_climate(discovery_info))

    async_add_entities(entities)


async def get_climate(discovery_info):
    """Create ZHA climate entity."""
    zha_dev = discovery_info.get('zha_device')
    if zha_dev is not None:
        manufacturer = zha_dev.manufacturer
        if manufacturer.startswith('Sinope Technologies'):
            thermostat = SinopeTechnologiesThermostat(**discovery_info)
    else:
        thermostat = Thermostat(**discovery_info)

    return thermostat


class Thermostat(ZhaEntity, ClimateDevice):
    """Representation of a ZHA Thermostat device."""

    _domain = DOMAIN
    _features = SUPPORT_OPERATION_MODE
    value_attribute = 0x0000

    def __init__(self, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(**kwargs)
        self._thrm = self.cluster_channels.get(THERMOSTAT_CHANNEL)
        self._support_flags = self._features
        self._target_temp = None

    @property
    def current_operation(self) -> Optional[str]:
        """Return current operation ie. heat, cool, idle."""
        operation = SYSTEM_MODE.get(self._thrm.system_mode)
        if operation is None:
            _LOGGER.error("%s: can't map 'system_mode: %s' to any operation",
                          self.entity_id, self._thrm.system_mode)
        return operation

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._thrm.local_temp is None:
            return None
        return self._thrm.local_temp / ZCL_TEMP

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        data = {}
        if self.current_operation:
            data[ATTR_SYS_MODE] = '[{}]/{}'.format(
                self._thrm.system_mode, SYSTEM_MODE.get(
                    self._thrm.system_mode, 'unknown'))
        if self.running_mode:
            data[ATTR_RUNNING_MODE] = self.running_mode
        if self._thrm.setpoint_change_source:
            data[ATTR_SETPT_CHANGE_SRC] = self._thrm.setpoint_change_source
        if self._thrm.setpoint_change_amount:
            data[ATTR_SETPT_CHANGE_AMT] = self._thrm.setpoint_change_amount
        if self._thrm.occupancy:
            data[ATTR_OCCUPANCY] = self._thrm.occupancy
        if self._thrm.occupied_cooling_setpoint:
            data[ATTR_OCCP_COOL_SETPT] = self._thrm.occupied_cooling_setpoint
        if self._thrm.occupied_heating_setpoint:
            data[ATTR_OCCP_HEAT_SETPT] = self._thrm.occupied_heating_setpoint

        unoccupied_cooling_setpoint = self._thrm.unoccupied_cooling_setpoint
        if unoccupied_cooling_setpoint:
            data[ATTR_UNACCP_HEAT_SETPT] = unoccupied_cooling_setpoint

        unoccupied_heating_setpoint = self._thrm.unoccupied_heating_setpoint
        if unoccupied_heating_setpoint:
            data[ATTR_UNACCP_COOL_SETPT] = unoccupied_heating_setpoint
        return data

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        if self._thrm.occupancy is None:
            return None
        return not bool(self._thrm.occupancy)

    @property
    def is_on(self):
        """Return true if on."""
        is_on = None
        if self.current_operation == STATE_OFF:
            is_on = False
        elif self._thrm.pi_cooling_demand > 0 or \
                self._thrm.pi_heating_demand > 0:
            is_on = True
        return is_on

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if STATE_COOL not in self.operation_list:
            result = self._thrm.abs_max_heat_setpoint_limit
        else:
            result = self._thrm.abs_max_cool_setpoint_limit
        if result is None:
            return result
        return round(result / ZCL_TEMP, 1)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if STATE_HEAT not in self.operation_list:
            result = self._thrm.abs_min_cool_setpoint_limit
        else:
            result = self._thrm.abs_min_heat_setpoint_limit
        if result is None:
            return result
        return round(result / ZCL_TEMP, 1)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return SEQ_OF_OPERATION.get(self._thrm.ctrl_seqe_of_oper, [STATE_OFF])

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def running_mode(self):
        """Return the current running mode of the system."""
        if self._thrm.running_mode is None:
            return None
        mode = RUNNING_MODE.get(self._thrm.running_mode, 'unknown')
        return mode

    @property
    def supported_features(self):
        """Return the list of supported features."""
        self._update_support_flags()
        return self._support_flags

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        temp = None
        if self.current_operation == STATE_COOL:
            if self.is_away_mode_on:
                temp = self._thrm.unoccupied_cooling_setpoint
            else:
                temp = self._thrm.occupied_cooling_setpoint
        elif self.current_operation == STATE_HEAT:
            if self.is_away_mode_on:
                temp = self._thrm.unoccupied_heating_setpoint
            else:
                temp = self._thrm.occupied_heating_setpoint
        if temp is None:
            return self._target_temp
        return round(temp / ZCL_TEMP, 1)

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            if self.is_away_mode_on:
                temp = self._thrm.unoccupied_cooling_setpoint / ZCL_TEMP
            else:
                temp = self._thrm.occupied_cooling_setpoint / ZCL_TEMP
            return round(temp, 1)
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            if self.is_away_mode_on:
                temp = self._thrm.unoccupied_heating_setpoint / ZCL_TEMP
            else:
                temp = self._thrm.occupied_heating_setpoint / ZCL_TEMP
            return round(temp, 1)
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    def async_attribute_updated(self, record):
        """Handle attribute update from device."""
        self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        operation_mode = kwargs.get(ATTR_OPERATION_MODE)

        _LOGGER.info("%s: target temperature %s", self.entity_id, temp)
        _LOGGER.info("%s: low temperature %s", self.entity_id, low_temp)
        _LOGGER.info("%s: high temperature %s", self.entity_id, high_temp)
        _LOGGER.info("%s: operation mode: %s", self.entity_id, operation_mode)

        if operation_mode is not None:
            await self.async_set_operation_mode(operation_mode)

        thrm = self._thrm
        if self.current_operation == STATE_AUTO:
            success = True
            if low_temp is not None:
                low_temp = int(low_temp * ZCL_TEMP)
                success = success and await thrm.async_set_heating_setpoint(
                    low_temp, self.is_away_mode_on)
            if high_temp is not None:
                high_temp = int(high_temp * ZCL_TEMP)
                success = success and await thrm.async_set_cooling_setpoint(
                    high_temp, self.is_away_mode_on)
        elif temp is not None:
            temp = int(temp * ZCL_TEMP)
            success = True
            if STATE_COOL in self.operation_list:
                success = success and await thrm.async_set_cooling_setpoint(
                    temp, self.is_away_mode_on
                )
            elif STATE_HEAT in self.operation_list:
                success = success and await thrm.async_set_heating_setpoint(
                    temp, self.is_away_mode_on
                )
            if success:
                self._target_temp = temp / ZCL_TEMP
        else:
            _LOGGER.error(
                'Missing valid argument for set_temperature in %s', kwargs)
            return

        if success:
            self.async_schedule_update_ha_state()
        return

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        if operation_mode in self.operation_list:
            system_mode = STATE_2_SYSTEM_MODE.get(operation_mode)
            if system_mode is None:
                _LOGGER.error("%s: Couldn't map operation %s to system_mode",
                              self.entity_id, operation_mode)
                system_mode = STATE_2_SYSTEM_MODE[STATE_OFF]
            await self._thrm.async_set_operation_mode(system_mode)
            self.async_schedule_update_ha_state()
        else:
            _LOGGER.error("%s: wrong op. mode: '%s'. Supported modes: %s",
                          self.entity_id, operation_mode, self.operation_list)

    def _update_support_flags(self):
        """Update support flags.

        depending on supported operation list
        """
        if self.operation_list is not None:
            if STATE_COOL in self.operation_list or \
                    STATE_HEAT in self.operation_list:
                self._support_flags |= SUPPORT_TARGET_TEMPERATURE
                self._support_flags |= SUPPORT_OPERATION_MODE
        if STATE_AUTO in self.operation_list:
            self._support_flags |= SUPPORT_TARGET_TEMPERATURE_HIGH
            self._support_flags |= SUPPORT_TARGET_TEMPERATURE_LOW

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        pass

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        pass

    async def async_update_outdoor_temperature(self, temperature):
        """Update outdoor temperature display."""
        pass

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._thrm, SIGNAL_ATTR_UPDATED, self.async_attribute_updated)


class SinopeTechnologiesThermostat(Thermostat):
    """Sinope Technologies Thermostat."""

    _features = SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE
    manufacturer = 0x119c
    update_time_interval = timedelta(minutes=15)

    async def async_added_to_hass(self):
        """Run when about to be added to Hass."""
        await super().async_added_to_hass()
        #async_track_time_interval(self.hass, self._async_update_time,
        #                          self.update_time_interval)
        #async_call_later(self.hass, randint(30, 45), self._async_update_time)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        if await self._thrm.async_set_occupancy(is_away=True):
            self.async_schedule_update_ha_state()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        if await self._thrm.async_set_occupancy(is_away=False):
            self.async_schedule_update_ha_state()

    async def async_update_outdoor_temperature(self, temperature):
        """Update Outdoor temperature display service call."""
        outdoor_temp = convert_temperature(
            temperature, self.hass.config.units.temperature_unit, TEMP_CELSIUS)
        outdoor_temp = int(outdoor_temp * ZCL_TEMP)
        _LOGGER.debug('%s: Updating outdoor temp to %s',
                      self.entity_id, outdoor_temp)
        cluster = self.endpoint.sinope_manufacturer_specific
        res = await cluster.write_attributes(
            {'outdoor_temp': outdoor_temp}, manufacturer=self.manufacturer
        )
        _LOGGER.debug("%s: Write Attr: %s", self.entity_id, res)

    async def _async_update_time(self, timestamp=None):
        """Update thermostat's time display."""

        secs_since_2k = int(time.mktime(time.localtime()) - SECS_2000_01_01)
        _LOGGER.debug("%s: Updating time: %s", self.entity_id, secs_since_2k)
        cluster = self.endpoint.sinope_manufacturer_specific
        res = await cluster.write_attributes(
            {'secs_since_2k': secs_since_2k}, manufacturer=self.manufacturer
        )
        _LOGGER.debug("%s: Write Attr: %s", self.entity_id, res)
