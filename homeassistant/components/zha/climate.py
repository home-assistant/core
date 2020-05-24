"""
Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""
from datetime import datetime, timedelta
import enum
import functools
import logging
from random import randint
from typing import List, Optional, Tuple

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN,
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .core import discovery
from .core.const import (
    CHANNEL_FAN,
    CHANNEL_THERMOSTAT,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

DEPENDENCIES = ["zha"]

ATTR_SYS_MODE = "system_mode"
ATTR_RUNNING_MODE = "running_mode"
ATTR_SETPT_CHANGE_SRC = "setpoint_change_source"
ATTR_SETPT_CHANGE_AMT = "setpoint_change_amount"
ATTR_OCCUPANCY = "occupancy"
ATTR_PI_COOLING_DEMAND = "pi_cooling_demand"
ATTR_PI_HEATING_DEMAND = "pi_heating_demand"
ATTR_OCCP_COOL_SETPT = "occupied_cooling_setpoint"
ATTR_OCCP_HEAT_SETPT = "occupied_heating_setpoint"
ATTR_UNOCCP_HEAT_SETPT = "unoccupied_heating_setpoint"
ATTR_UNOCCP_COOL_SETPT = "unoccupied_cooling_setpoint"


STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)
RUNNING_MODE = {0x00: HVAC_MODE_OFF, 0x03: HVAC_MODE_COOL, 0x04: HVAC_MODE_HEAT}


class ThermostatFanMode(enum.IntEnum):
    """Fan channel enum for thermostat Fans."""

    OFF = 0x00
    ON = 0x04
    AUTO = 0x05


class RunningState(enum.IntFlag):
    """ZCL Running state enum."""

    HEAT = 0x0001
    COOL = 0x0002
    FAN = 0x0004
    HEAT_STAGE_2 = 0x0008
    COOL_STAGE_2 = 0x0010
    FAN_STAGE_2 = 0x0020
    FAN_STAGE_3 = 0x0040


SEQ_OF_OPERATION = {
    0x00: (HVAC_MODE_OFF, HVAC_MODE_COOL),  # cooling only
    0x01: (HVAC_MODE_OFF, HVAC_MODE_COOL),  # cooling with reheat
    0x02: (HVAC_MODE_OFF, HVAC_MODE_HEAT),  # heating only
    0x03: (HVAC_MODE_OFF, HVAC_MODE_HEAT),  # heating with reheat
    # cooling and heating 4-pipes
    0x04: (HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT),
    # cooling and heating 4-pipes
    0x05: (HVAC_MODE_OFF, HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT),
    0x06: (HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF),  # centralite specific
    0x07: (HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF),  # centralite specific
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]
    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


@STRICT_MATCH(channel_names=CHANNEL_THERMOSTAT, aux_channels=CHANNEL_FAN)
class Thermostat(ZhaEntity, ClimateEntity):
    """Representation of a ZHA Thermostat device."""

    DEFAULT_MAX_TEMP = 35
    DEFAULT_MIN_TEMP = 7

    _domain = DOMAIN
    value_attribute = 0x0000

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._thrm = self.cluster_channels.get(CHANNEL_THERMOSTAT)
        self._preset = PRESET_NONE
        self._presets = []
        self._supported_flags = SUPPORT_TARGET_TEMPERATURE
        self._fan = self.cluster_channels.get(CHANNEL_FAN)

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
            mode = SYSTEM_MODE_2_HVAC.get(self._thrm.system_mode, "unknown")
            data[ATTR_SYS_MODE] = f"[{self._thrm.system_mode}]/{mode}"
        if self._thrm.occupancy is not None:
            data[ATTR_OCCUPANCY] = self._thrm.occupancy
        if self._thrm.occupied_cooling_setpoint is not None:
            data[ATTR_OCCP_COOL_SETPT] = self._thrm.occupied_cooling_setpoint
        if self._thrm.occupied_heating_setpoint is not None:
            data[ATTR_OCCP_HEAT_SETPT] = self._thrm.occupied_heating_setpoint

        unoccupied_cooling_setpoint = self._thrm.unoccupied_cooling_setpoint
        if unoccupied_cooling_setpoint is not None:
            data[ATTR_UNOCCP_HEAT_SETPT] = unoccupied_cooling_setpoint

        unoccupied_heating_setpoint = self._thrm.unoccupied_heating_setpoint
        if unoccupied_heating_setpoint is not None:
            data[ATTR_UNOCCP_COOL_SETPT] = unoccupied_heating_setpoint
        return data

    @property
    def fan_mode(self) -> Optional[str]:
        """Return current FAN mode."""
        if self._thrm.running_state is None:
            return FAN_AUTO

        if self._thrm.running_state & (
            RunningState.FAN | RunningState.FAN_STAGE_2 | RunningState.FAN_STAGE_3
        ):
            return FAN_ON
        return FAN_AUTO

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return supported FAN modes."""
        if not self._fan:
            return None
        return [FAN_AUTO, FAN_ON]

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current HVAC action."""
        if (
            self._thrm.pi_heating_demand is None
            and self._thrm.pi_cooling_demand is None
        ):
            return self._rm_rs_action
        return self._pi_demand_action

    @property
    def _rm_rs_action(self) -> Optional[str]:
        """Return the current HVAC action based on running mode and running state."""

        running_mode = self._thrm.running_mode
        if running_mode == SystemMode.HEAT:
            return CURRENT_HVAC_HEAT
        if running_mode == SystemMode.COOL:
            return CURRENT_HVAC_COOL

        running_state = self._thrm.running_state
        if running_state and running_state & (
            RunningState.FAN | RunningState.FAN_STAGE_2 | RunningState.FAN_STAGE_3
        ):
            return CURRENT_HVAC_FAN
        if self.hvac_mode != HVAC_MODE_OFF and running_mode == SystemMode.OFF:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF

    @property
    def _pi_demand_action(self) -> Optional[str]:
        """Return the current HVAC action based on pi_demands."""

        heating_demand = self._thrm.pi_heating_demand
        if heating_demand is not None and heating_demand > 0:
            return CURRENT_HVAC_HEAT
        cooling_demand = self._thrm.pi_cooling_demand
        if cooling_demand is not None and cooling_demand > 0:
            return CURRENT_HVAC_COOL

        if self.hvac_mode != HVAC_MODE_OFF:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return HVAC operation mode."""
        return SYSTEM_MODE_2_HVAC.get(self._thrm.system_mode)

    @property
    def hvac_modes(self) -> Tuple[str, ...]:
        """Return the list of available HVAC operation modes."""
        return SEQ_OF_OPERATION.get(self._thrm.ctrl_seqe_of_oper, (HVAC_MODE_OFF,))

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def preset_mode(self) -> Optional[str]:
        """Return current preset mode."""
        return self._preset

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return supported preset modes."""
        return self._presets

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = self._supported_flags
        if HVAC_MODE_HEAT_COOL in self.hvac_modes:
            features |= SUPPORT_TARGET_TEMPERATURE_RANGE
        if self._fan is not None:
            self._supported_flags |= SUPPORT_FAN_MODE
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

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._thrm, SIGNAL_ATTR_UPDATED, self.async_attribute_updated
        )

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
                self._preset = PRESET_NONE

        self.debug("Attribute '%s' = %s update", record.attr_name, record.value)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if fan_mode not in self.fan_modes:
            self.warning("Unsupported '%s' fan mode", fan_mode)
            return

        if fan_mode == FAN_ON:
            mode = ThermostatFanMode.ON
        else:
            mode = ThermostatFanMode.AUTO

        await self._fan.async_set_speed(mode)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        if hvac_mode not in self.hvac_modes:
            self.warning(
                "can't set '%s' mode. Supported modes are: %s",
                hvac_mode,
                self.hvac_modes,
            )
            return

        if await self._thrm.async_set_operation_mode(HVAC_MODE_2_SYSTEM[hvac_mode]):
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self.preset_modes:
            self.debug("preset mode '%s' is not supported", preset_mode)
            return

        if self.preset_mode not in (preset_mode, PRESET_NONE):
            if not await self.async_preset_handler(self.preset_mode, enable=False):
                self.debug("Couldn't turn off '%s' preset", self.preset_mode)
                return

        if preset_mode != PRESET_NONE:
            if not await self.async_preset_handler(preset_mode, enable=True):
                self.debug("Couldn't turn on '%s' preset", preset_mode)
                return
        self._preset = preset_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

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
                self.debug("Setting heating %s setpoint: %s", low_temp, success)
            if high_temp is not None:
                high_temp = int(high_temp * ZCL_TEMP)
                success = success and await thrm.async_set_cooling_setpoint(
                    high_temp, self.preset_mode == PRESET_AWAY
                )
                self.debug("Setting cooling %s setpoint: %s", low_temp, success)
        elif temp is not None:
            temp = int(temp * ZCL_TEMP)
            if self.hvac_mode == HVAC_MODE_COOL:
                success = await thrm.async_set_cooling_setpoint(
                    temp, self.preset_mode == PRESET_AWAY
                )
            elif self.hvac_mode == HVAC_MODE_HEAT:
                success = await thrm.async_set_heating_setpoint(
                    temp, self.preset_mode == PRESET_AWAY
                )
            else:
                self.debug("Not setting temperature for '%s' mode", self.hvac_mode)
                return
        else:
            self.debug("incorrect %s setting for '%s' mode", kwargs, self.hvac_mode)
            return

        if success:
            self.async_write_ha_state()

    async def async_preset_handler(self, preset: str, enable: bool = False) -> bool:
        """Set the preset mode via handler."""

        handler = getattr(self, f"async_preset_handler_{preset}")
        return await handler(enable)


@STRICT_MATCH(
    channel_names={CHANNEL_THERMOSTAT, "sinope_manufacturer_specific"},
    manufacturers="Sinope Technologies",
)
class SinopeTechnologiesThermostat(Thermostat):
    """Sinope Technologies Thermostat."""

    manufacturer = 0x119C
    update_time_interval = timedelta(minutes=randint(45, 75))

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._presets = [PRESET_AWAY, PRESET_NONE]
        self._supported_flags |= SUPPORT_PRESET_MODE
        self._manufacturer_ch = self.cluster_channels["sinope_manufacturer_specific"]

    @callback
    def _async_update_time(self, timestamp=None) -> None:
        """Update thermostat's time display."""

        secs_2k = (
            dt_util.now().replace(tzinfo=None) - datetime(2000, 1, 1, 0, 0, 0, 0)
        ).total_seconds()

        self.debug("Updating time: %s", secs_2k)
        self._manufacturer_ch.cluster.create_catching_task(
            self._manufacturer_ch.cluster.write_attributes(
                {"secs_since_2k": secs_2k}, manufacturer=self.manufacturer
            )
        )

    async def async_added_to_hass(self):
        """Run when about to be added to Hass."""
        await super().async_added_to_hass()
        async_track_time_interval(
            self.hass, self._async_update_time, self.update_time_interval
        )
        self._async_update_time()

    async def async_preset_handler_away(self, is_away: bool = False) -> bool:
        """Set occupancy."""
        mfg_code = self._zha_device.manufacturer_code
        res = await self._thrm.write_attributes(
            {"set_occupancy": 0 if is_away else 1}, manufacturer=mfg_code
        )

        self.debug("set occupancy to %s. Status: %s", 0 if is_away else 1, res)
        return res


@STRICT_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    aux_channels=CHANNEL_FAN,
    manufacturers="Zen Within",
)
class ZenWithinThermostat(Thermostat):
    """Zen Within Thermostat implementation."""

    @property
    def _rm_rs_action(self) -> Optional[str]:
        """Return the current HVAC action based on running mode and running state."""

        running_state = self._thrm.running_state
        if running_state is None:
            return None
        if running_state & (RunningState.HEAT | RunningState.HEAT_STAGE_2):
            return CURRENT_HVAC_HEAT
        if running_state & (RunningState.COOL | RunningState.COOL_STAGE_2):
            return CURRENT_HVAC_COOL
        if running_state & (
            RunningState.FAN | RunningState.FAN_STAGE_2 | RunningState.FAN_STAGE_3
        ):
            return CURRENT_HVAC_FAN

        if self.hvac_mode != HVAC_MODE_OFF:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF
