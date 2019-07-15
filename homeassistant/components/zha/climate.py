"""
Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""
from datetime import timedelta
import enum
import logging
from random import randint
import time
from typing import List, Optional

from zigpy.zcl.foundation import Status

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
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
    0x00: [HVAC_MODE_OFF, HVAC_MODE_COOL],  # cooling only
    0x01: [HVAC_MODE_OFF, HVAC_MODE_COOL],  # cooling with reheat
    0x02: [HVAC_MODE_OFF, HVAC_MODE_HEAT],  # heating only
    0x03: [HVAC_MODE_OFF, HVAC_MODE_HEAT],  # heating with reheat
    # cooling and heating 4-pipes
    0x04: [HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT],
    # cooling and heating 4-pipes
    0x05: [HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT],
}


class SystemMode(enum.IntEnum):
    """ZCL System Mode attribute enum."""

    OFF = 0x00
    HEAT_COOL = 0x01
    COOL = 0x03
    HEAT = 0x04
    AUX_HEAT = 0x05
    PRE_COOL = 0x06
    FAN_ONLY = 0x07
    DRY = 0x08
    SLEEP = 0x09


HVAC_MODE_2_SYSTEM = {
    HVAC_MODE_OFF: SystemMode.OFF,
    HVAC_MODE_HEAT_COOL: SystemMode.HEAT_COOL,
    HVAC_MODE_COOL: SystemMode.COOL,
    HVAC_MODE_HEAT: SystemMode.HEAT,
    HVAC_MODE_FAN_ONLY: SystemMode.FAN_ONLY,
    HVAC_MODE_DRY: SystemMode.DRY,
}

SYSTEM_MODE_2_HVAC = {
    SystemMode.OFF: HVAC_MODE_OFF,
    SystemMode.HEAT_COOL: HVAC_MODE_HEAT_COOL,
    SystemMode.COOL: HVAC_MODE_COOL,
    SystemMode.HEAT: HVAC_MODE_HEAT,
    SystemMode.AUX_HEAT: HVAC_MODE_HEAT,
    SystemMode.PRE_COOL: HVAC_MODE_COOL,  # this is 'precooling'. is it the same?
    SystemMode.FAN_ONLY: HVAC_MODE_FAN_ONLY,
    SystemMode.DRY: HVAC_MODE_DRY,
    SystemMode.SLEEP: HVAC_MODE_OFF,
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

    DEFAULT_MAX_TEMP = 35
    DEFAULT_MIN_TEMP = 7

    _domain = DOMAIN
    value_attribute = 0x0000

    def __init__(self, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(**kwargs)
        self._thrm = self.cluster_channels.get(THERMOSTAT_CHANNEL)
        self._preset = None
        self._presets = None
        self._supported_flags = SUPPORT_TARGET_TEMPERATURE
        if FAN_CHANNEL in self.cluster_channels:
            self._supported_flags |= SUPPORT_FAN_MODE
        self._target_temp = None
        self._target_range = (None, None)

    @property
    def preset_mode(self) -> Optional[str]:
        return self._preset

    @property
    def preset_modes(self) -> Optional[List[str]]:
        return self._presets

    @property
    def hvac_mode(self) -> str:
        """Return current HVAC operation mode."""
        mode = SYSTEM_MODE_2_HVAC.get(self._thrm.system_mode)
        if mode is None:
            self.error(
                "can't map 'system_mode: %s' to a HVAC mode", self._thrm.system_mode
            )
        return mode

    @property
    def is_aux_heat(self) -> Optional[bool]:
        """Return True if aux heat is on."""
        return self._thrm.system_mode == SystemMode.AUX_HEAT

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
        if self.hvac_mode:
            data[ATTR_SYS_MODE] = "[{}]/{}".format(
                self._thrm.system_mode,
                SYSTEM_MODE_2_HVAC.get(self._thrm.system_mode, "unknown"),
            )
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
            data[ATTR_UNOCCP_HEAT_SETPT] = unoccupied_cooling_setpoint

        unoccupied_heating_setpoint = self._thrm.unoccupied_heating_setpoint
        if unoccupied_heating_setpoint:
            data[ATTR_UNOCCP_COOL_SETPT] = unoccupied_heating_setpoint
        return data

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available HVAC operation modes."""
        return SEQ_OF_OPERATION.get(self._thrm.ctrl_seqe_of_oper, [HVAC_MODE_OFF])

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current HVAC action."""
        if self._thrm.running_mode is None:
            return None
        action = RUNNING_MODE.get(self._thrm.running_mode)
        if action == CURRENT_HVAC_IDLE and self.hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF
        return action

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = self._supported_flags
        if HVAC_MODE_HEAT_COOL in self.hvac_modes:
            features |= SUPPORT_TARGET_TEMPERATURE_RANGE
        return features

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        temp = None
        if self.hvac_mode == HVAC_MODE_COOL:
            if self.preset_mode == PRESET_AWAY:
                temp = self._thrm.unoccupied_cooling_setpoint
            else:
                temp = self._thrm.occupied_cooling_setpoint
        elif self.hvac_mode == HVAC_MODE_HEAT:
            if self.preset_mode == PRESET_AWAY:
                temp = self._thrm.unoccupied_heating_setpoint
            else:
                temp = self._thrm.occupied_heating_setpoint
        if temp is None:
            return temp
        return round(temp / ZCL_TEMP, 1)

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.hvac_mode != HVAC_MODE_HEAT_COOL:
            return None
        if self.preset_mode == PRESET_AWAY:
            temp = self._thrm.unoccupied_cooling_setpoint
        else:
            temp = self._thrm.occupied_cooling_setpoint

        if temp is None:
            return temp

        return round(temp / ZCL_TEMP, 1)

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.hvac_mode != HVAC_MODE_HEAT_COOL:
            return None
        if self.preset_mode == PRESET_AWAY:
            temp = self._thrm.unoccupied_heating_setpoint
        else:
            temp = self._thrm.occupied_heating_setpoint

        if temp is None:
            return temp
        return round(temp / ZCL_TEMP, 1)

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        temps = []
        if HVAC_MODE_HEAT in self.hvac_modes:
            temps.append(self._thrm.max_heat_setpoint_limit)
        if HVAC_MODE_COOL in self.hvac_modes:
            temps.append(self._thrm.max_cool_setpoint_limit)

        if not temps:
            return self.DEFAULT_MAX_TEMP
        return round(max(temps) / ZCL_TEMP, 1)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        temps = []
        if HVAC_MODE_HEAT in self.hvac_modes:
            temps.append(self._thrm.min_heat_setpoint_limit)
        if HVAC_MODE_COOL in self.hvac_modes:
            temps.append(self._thrm.min_cool_setpoint_limit)

        if not temps:
            return self.DEFAULT_MIN_TEMP
        return round(min(temps) / ZCL_TEMP, 1)

    async def async_attribute_updated(self, record):
        """Handle attribute update from device."""
        if (
            record.attr_name in (ATTR_OCCP_COOL_SETPT, ATTR_OCCP_HEAT_SETPT)
            and self.preset_mode == PRESET_AWAY
        ):
            # occupancy attribute is an unreportable attribute, but if we get
            # an attribute update for an "occupied" setpoint, there's a chance
            # occupancy has changed
            occupancy = await self._thrm.get_occupancy()
            if occupancy is True:
                self._preset = None

        self.async_schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        self.debug("target temperature %s", temp)
        self.debug("low temperature %s", low_temp)
        self.debug("high temperature %s", high_temp)
        self.debug("operation mode: %s", hvac_mode)

        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

        thrm = self._thrm
        if self.hvac_mode == HVAC_MODE_HEAT_COOL:
            success = True
            if low_temp is not None:
                low_temp = int(low_temp * ZCL_TEMP)
                success = success and await thrm.async_set_heating_setpoint(
                    low_temp, self.preset_mode == PRESET_AWAY
                )
            if high_temp is not None:
                high_temp = int(high_temp * ZCL_TEMP)
                success = success and await thrm.async_set_cooling_setpoint(
                    high_temp, self.preset_mode == PRESET_AWAY
                )
        elif temp is not None:
            temp = int(temp * ZCL_TEMP)
            success = True
            if self.hvac_mode == HVAC_MODE_COOL:
                success = success and await thrm.async_set_cooling_setpoint(
                    temp, self.preset_mode == PRESET_AWAY
                )
            elif self.hvac_mode == HVAC_MODE_HEAT:
                success = success and await thrm.async_set_heating_setpoint(
                    temp, self.preset_mode == PRESET_AWAY
                )
            else:
                self.debug("Not setting temperature for '%s' mode", self.hvac_mode)
                success = False
            if success:
                self._target_temp = temp / ZCL_TEMP
        else:
            success = False
            self.debug(
                "not setting temperature %s for '%s' mode", kwargs, self.hvac_mode
            )
        if success:
            self.async_schedule_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode not in self.hvac_modes:
            self.warn(
                "can't set '%s' mode. Supported modes are: %s",
                hvac_mode,
                self.hvac_modes,
            )
            return

        system_mode = HVAC_MODE_2_SYSTEM.get(hvac_mode)
        if system_mode is None:
            self.error("Couldn't map operation %s to system_mode", hvac_mode)
            return

        if await self._thrm.async_set_operation_mode(system_mode):
            self.async_schedule_update_ha_state()

    async def async_update_outdoor_temperature(self, temperature):
        """Update outdoor temperature display."""
        pass

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._thrm, SIGNAL_ATTR_UPDATED, self.async_attribute_updated)

    async def async_turn_aux_heat_off(self) -> None:
        """Turn off aux heater."""
        if await self._thrm.async_set_operation_mode(SystemMode.HEAT):
            self.async_schedule_update_ha_state()

    async def async_turn_aux_heat_on(self) -> None:
        """Turn on aux heater."""
        if await self._thrm.async_set_operation_mode(SystemMode.AUX_HEAT):
            self.async_schedule_update_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode and preset_mode not in self.preset_modes:
            self.debug("preset mode '%s' is not supported", preset_mode)
            return

        if self.preset_mode and self.preset_mode != preset_mode:
            if not await self.preset_handler(self.preset_mode, enable=False):
                self.debug("Couldn't turn off '%s' preset", self.preset_mode)
                return

        if preset_mode is not None:
            if not await self.preset_handler(preset_mode, enable=True):
                self.debug("Couldn't turn on '%s' preset", preset_mode)
                return
        self._preset = preset_mode
        self.async_schedule_update_ha_state()

    async def preset_handler(self, preset: str, enable: bool = False) -> bool:
        handler = getattr(self, f"async_preset_handler_{preset}", None)
        if handler is None:
            self.warn("No '%s' preset handler", preset)
            return

        return await handler(enable)


class SinopeTechnologiesThermostat(Thermostat):
    """Sinope Technologies Thermostat."""

    manufacturer = 0x119C
    update_time_interval = timedelta(minutes=15)

    def __init__(self, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(**kwargs)
        self._presets = [PRESET_AWAY]
        self._supported_flags |= SUPPORT_PRESET_MODE

    async def async_added_to_hass(self):
        """Run when about to be added to Hass."""
        await super().async_added_to_hass()
        #async_track_time_interval(self.hass, self._async_update_time,
        #                          self.update_time_interval)
        #async_call_later(self.hass, randint(30, 45), self._async_update_time)

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        if await self.async_set_occupancy(is_away=True):
            self.async_schedule_update_ha_state()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        if await self.async_set_occupancy(is_away=False):
            self.async_schedule_update_ha_state()

    async def async_update_outdoor_temperature(self, temperature):
        """Update Outdoor temperature display service call."""
        outdoor_temp = convert_temperature(
            temperature, self.hass.config.units.temperature_unit, TEMP_CELSIUS)
        outdoor_temp = int(outdoor_temp * ZCL_TEMP)
        self.debug("Updating outdoor temp to %s", outdoor_temp)
        cluster = self.endpoint.sinope_manufacturer_specific
        res = await cluster.write_attributes(
            {'outdoor_temp': outdoor_temp}, manufacturer=self.manufacturer
        )
        self.debug("Write Attr: %s", res)

    async def _async_update_time(self, timestamp=None):
        """Update thermostat's time display."""

        secs_since_2k = int(time.mktime(time.localtime()) - SECS_2000_01_01)
        self.debug("Updating time: %s", secs_since_2k)
        cluster = self.endpoint.sinope_manufacturer_specific
        res = await cluster.write_attributes(
            {'secs_since_2k': secs_since_2k}, manufacturer=self.manufacturer
        )
        self.debug("Write Attr: %s", res)

    async def async_preset_handler_away(self, is_away: bool = False) -> bool:
        """Set occupancy."""
        mfg_code = self._zha_device.manufacturer_code
        res = await self._thrm.write_attributes(
            {"set_occupancy": 0 if is_away else 1}, manufacturer=mfg_code
        )

        self.debug("set occupancy to %s. Status: %s", 0 if is_away else 1, res)
        return res
