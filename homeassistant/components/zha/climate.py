"""
Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""
from __future__ import annotations

from datetime import datetime, timedelta
import functools
from random import randint

from zigpy.zcl.clusters.hvac import Fan as F, Thermostat as T

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .core import discovery
from .core.const import (
    CHANNEL_FAN,
    CHANNEL_THERMOSTAT,
    DATA_ZHA,
    PRESET_COMPLEX,
    PRESET_SCHEDULE,
    PRESET_TEMP_MANUAL,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

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


STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.CLIMATE)
MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.CLIMATE)
RUNNING_MODE = {0x00: HVACMode.OFF, 0x03: HVACMode.COOL, 0x04: HVACMode.HEAT}

SEQ_OF_OPERATION = {
    0x00: [HVACMode.OFF, HVACMode.COOL],  # cooling only
    0x01: [HVACMode.OFF, HVACMode.COOL],  # cooling with reheat
    0x02: [HVACMode.OFF, HVACMode.HEAT],  # heating only
    0x03: [HVACMode.OFF, HVACMode.HEAT],  # heating with reheat
    # cooling and heating 4-pipes
    0x04: [HVACMode.OFF, HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.HEAT],
    # cooling and heating 4-pipes
    0x05: [HVACMode.OFF, HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.HEAT],
    0x06: [HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF],  # centralite specific
    0x07: [HVACMode.HEAT_COOL, HVACMode.OFF],  # centralite specific
}

HVAC_MODE_2_SYSTEM = {
    HVACMode.OFF: T.SystemMode.Off,
    HVACMode.HEAT_COOL: T.SystemMode.Auto,
    HVACMode.COOL: T.SystemMode.Cool,
    HVACMode.HEAT: T.SystemMode.Heat,
    HVACMode.FAN_ONLY: T.SystemMode.Fan_only,
    HVACMode.DRY: T.SystemMode.Dry,
}

SYSTEM_MODE_2_HVAC = {
    T.SystemMode.Off: HVACMode.OFF,
    T.SystemMode.Auto: HVACMode.HEAT_COOL,
    T.SystemMode.Cool: HVACMode.COOL,
    T.SystemMode.Heat: HVACMode.HEAT,
    T.SystemMode.Emergency_Heating: HVACMode.HEAT,
    T.SystemMode.Pre_cooling: HVACMode.COOL,  # this is 'precooling'. is it the same?
    T.SystemMode.Fan_only: HVACMode.FAN_ONLY,
    T.SystemMode.Dry: HVACMode.DRY,
    T.SystemMode.Sleep: HVACMode.OFF,
}

ZCL_TEMP = 100


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.CLIMATE]
    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@MULTI_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    aux_channels=CHANNEL_FAN,
    stop_on_match_group=CHANNEL_THERMOSTAT,
)
class Thermostat(ZhaEntity, ClimateEntity):
    """Representation of a ZHA Thermostat device."""

    DEFAULT_MAX_TEMP = 35
    DEFAULT_MIN_TEMP = 7

    _attr_precision = PRECISION_TENTHS
    _attr_temperature_unit = TEMP_CELSIUS

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._thrm = self.cluster_channels.get(CHANNEL_THERMOSTAT)
        self._preset = PRESET_NONE
        self._presets = []
        self._supported_flags = ClimateEntityFeature.TARGET_TEMPERATURE
        self._fan = self.cluster_channels.get(CHANNEL_FAN)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._thrm.local_temperature is None:
            return None
        return self._thrm.local_temperature / ZCL_TEMP

    @property
    def extra_state_attributes(self):
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
        if self._thrm.pi_heating_demand is not None:
            data[ATTR_PI_HEATING_DEMAND] = self._thrm.pi_heating_demand
        if self._thrm.pi_cooling_demand is not None:
            data[ATTR_PI_COOLING_DEMAND] = self._thrm.pi_cooling_demand

        unoccupied_cooling_setpoint = self._thrm.unoccupied_cooling_setpoint
        if unoccupied_cooling_setpoint is not None:
            data[ATTR_UNOCCP_COOL_SETPT] = unoccupied_cooling_setpoint

        unoccupied_heating_setpoint = self._thrm.unoccupied_heating_setpoint
        if unoccupied_heating_setpoint is not None:
            data[ATTR_UNOCCP_HEAT_SETPT] = unoccupied_heating_setpoint
        return data

    @property
    def fan_mode(self) -> str | None:
        """Return current FAN mode."""
        if self._thrm.running_state is None:
            return FAN_AUTO

        if self._thrm.running_state & (
            T.RunningState.Fan_State_On
            | T.RunningState.Fan_2nd_Stage_On
            | T.RunningState.Fan_3rd_Stage_On
        ):
            return FAN_ON
        return FAN_AUTO

    @property
    def fan_modes(self) -> list[str] | None:
        """Return supported FAN modes."""
        if not self._fan:
            return None
        return [FAN_AUTO, FAN_ON]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        if (
            self._thrm.pi_heating_demand is None
            and self._thrm.pi_cooling_demand is None
        ):
            return self._rm_rs_action
        return self._pi_demand_action

    @property
    def _rm_rs_action(self) -> HVACAction | None:
        """Return the current HVAC action based on running mode and running state."""

        if (running_state := self._thrm.running_state) is None:
            return None
        if running_state & (
            T.RunningState.Heat_State_On | T.RunningState.Heat_2nd_Stage_On
        ):
            return HVACAction.HEATING
        if running_state & (
            T.RunningState.Cool_State_On | T.RunningState.Cool_2nd_Stage_On
        ):
            return HVACAction.COOLING
        if running_state & (
            T.RunningState.Fan_State_On
            | T.RunningState.Fan_2nd_Stage_On
            | T.RunningState.Fan_3rd_Stage_On
        ):
            return HVACAction.FAN
        if running_state & T.RunningState.Idle:
            return HVACAction.IDLE
        if self.hvac_mode != HVACMode.OFF:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def _pi_demand_action(self) -> HVACAction | None:
        """Return the current HVAC action based on pi_demands."""

        heating_demand = self._thrm.pi_heating_demand
        if heating_demand is not None and heating_demand > 0:
            return HVACAction.HEATING
        cooling_demand = self._thrm.pi_cooling_demand
        if cooling_demand is not None and cooling_demand > 0:
            return HVACAction.COOLING

        if self.hvac_mode != HVACMode.OFF:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return HVAC operation mode."""
        return SYSTEM_MODE_2_HVAC.get(self._thrm.system_mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC operation modes."""
        return SEQ_OF_OPERATION.get(self._thrm.ctrl_sequence_of_oper, [HVACMode.OFF])

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self._preset

    @property
    def preset_modes(self) -> list[str] | None:
        """Return supported preset modes."""
        return self._presets

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = self._supported_flags
        if HVACMode.HEAT_COOL in self.hvac_modes:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self._fan is not None:
            self._supported_flags |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        temp = None
        if self.hvac_mode == HVACMode.COOL:
            if self.preset_mode == PRESET_AWAY:
                temp = self._thrm.unoccupied_cooling_setpoint
            else:
                temp = self._thrm.occupied_cooling_setpoint
        elif self.hvac_mode == HVACMode.HEAT:
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
        if self.hvac_mode != HVACMode.HEAT_COOL:
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
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        if self.preset_mode == PRESET_AWAY:
            temp = self._thrm.unoccupied_heating_setpoint
        else:
            temp = self._thrm.occupied_heating_setpoint

        if temp is None:
            return temp
        return round(temp / ZCL_TEMP, 1)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        temps = []
        if HVACMode.HEAT in self.hvac_modes:
            temps.append(self._thrm.max_heat_setpoint_limit)
        if HVACMode.COOL in self.hvac_modes:
            temps.append(self._thrm.max_cool_setpoint_limit)

        if not temps:
            return self.DEFAULT_MAX_TEMP
        return round(max(temps) / ZCL_TEMP, 1)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        temps = []
        if HVACMode.HEAT in self.hvac_modes:
            temps.append(self._thrm.min_heat_setpoint_limit)
        if HVACMode.COOL in self.hvac_modes:
            temps.append(self._thrm.min_cool_setpoint_limit)

        if not temps:
            return self.DEFAULT_MIN_TEMP
        return round(min(temps) / ZCL_TEMP, 1)

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
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
            if await self._thrm.get_occupancy() is True:
                self._preset = PRESET_NONE

        self.debug("Attribute '%s' = %s update", record.attr_name, record.value)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if not self.fan_modes or fan_mode not in self.fan_modes:
            self.warning("Unsupported '%s' fan mode", fan_mode)
            return

        if fan_mode == FAN_ON:
            mode = F.FanMode.On
        else:
            mode = F.FanMode.Auto

        await self._fan.async_set_speed(mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
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
        if not self.preset_modes or preset_mode not in self.preset_modes:
            self.debug("Preset mode '%s' is not supported", preset_mode)
            return

        if self.preset_mode not in (
            preset_mode,
            PRESET_NONE,
        ) and not await self.async_preset_handler(self.preset_mode, enable=False):
            self.debug("Couldn't turn off '%s' preset", self.preset_mode)
            return

        if preset_mode != PRESET_NONE and not await self.async_preset_handler(
            preset_mode, enable=True
        ):
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
        if self.hvac_mode == HVACMode.HEAT_COOL:
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
            if self.hvac_mode == HVACMode.COOL:
                success = await thrm.async_set_cooling_setpoint(
                    temp, self.preset_mode == PRESET_AWAY
                )
            elif self.hvac_mode == HVACMode.HEAT:
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


@MULTI_MATCH(
    channel_names={CHANNEL_THERMOSTAT, "sinope_manufacturer_specific"},
    manufacturers="Sinope Technologies",
    stop_on_match_group=CHANNEL_THERMOSTAT,
)
class SinopeTechnologiesThermostat(Thermostat):
    """Sinope Technologies Thermostat."""

    manufacturer = 0x119C
    update_time_interval = timedelta(minutes=randint(45, 75))

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._presets = [PRESET_AWAY, PRESET_NONE]
        self._supported_flags |= ClimateEntityFeature.PRESET_MODE
        self._manufacturer_ch = self.cluster_channels["sinope_manufacturer_specific"]

    @property
    def _rm_rs_action(self) -> HVACAction:
        """Return the current HVAC action based on running mode and running state."""

        running_mode = self._thrm.running_mode
        if running_mode == T.SystemMode.Heat:
            return HVACAction.HEATING
        if running_mode == T.SystemMode.Cool:
            return HVACAction.COOLING

        running_state = self._thrm.running_state
        if running_state and running_state & (
            T.RunningState.Fan_State_On
            | T.RunningState.Fan_2nd_Stage_On
            | T.RunningState.Fan_3rd_Stage_On
        ):
            return HVACAction.FAN
        if self.hvac_mode != HVACMode.OFF and running_mode == T.SystemMode.Off:
            return HVACAction.IDLE
        return HVACAction.OFF

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


@MULTI_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    aux_channels=CHANNEL_FAN,
    manufacturers={"Zen Within", "LUX"},
    stop_on_match_group=CHANNEL_THERMOSTAT,
)
class ZenWithinThermostat(Thermostat):
    """Zen Within Thermostat implementation."""


@MULTI_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    aux_channels=CHANNEL_FAN,
    manufacturers="Centralite",
    models={"3157100", "3157100-E"},
    stop_on_match_group=CHANNEL_THERMOSTAT,
)
class CentralitePearl(ZenWithinThermostat):
    """Centralite Pearl Thermostat implementation."""


@STRICT_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    manufacturers={
        "_TZE200_ckud7u2l",
        "_TZE200_ywdxldoj",
        "_TZE200_cwnjrr72",
        "_TZE200_2atgpdho",
        "_TZE200_pvvbommb",
        "_TZE200_4eeyebrt",
        "_TZE200_cpmgn2cf",
        "_TZE200_9sfg7gm0",
        "_TYST11_ckud7u2l",
        "_TYST11_ywdxldoj",
        "_TYST11_cwnjrr72",
        "_TYST11_2atgpdho",
    },
)
class MoesThermostat(Thermostat):
    """Moes Thermostat implementation."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._presets = [
            PRESET_NONE,
            PRESET_AWAY,
            PRESET_SCHEDULE,
            PRESET_COMFORT,
            PRESET_ECO,
            PRESET_BOOST,
            PRESET_COMPLEX,
        ]
        self._supported_flags |= ClimateEntityFeature.PRESET_MODE

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return only the heat mode, because the device can't be turned off."""
        return [HVACMode.HEAT]

    async def async_attribute_updated(self, record):
        """Handle attribute update from device."""
        if record.attr_name == "operation_preset":
            if record.value == 0:
                self._preset = PRESET_AWAY
            if record.value == 1:
                self._preset = PRESET_SCHEDULE
            if record.value == 2:
                self._preset = PRESET_NONE
            if record.value == 3:
                self._preset = PRESET_COMFORT
            if record.value == 4:
                self._preset = PRESET_ECO
            if record.value == 5:
                self._preset = PRESET_BOOST
            if record.value == 6:
                self._preset = PRESET_COMPLEX
        await super().async_attribute_updated(record)

    async def async_preset_handler(self, preset: str, enable: bool = False) -> bool:
        """Set the preset mode."""
        mfg_code = self._zha_device.manufacturer_code
        if not enable:
            return await self._thrm.write_attributes(
                {"operation_preset": 2}, manufacturer=mfg_code
            )
        if preset == PRESET_AWAY:
            return await self._thrm.write_attributes(
                {"operation_preset": 0}, manufacturer=mfg_code
            )
        if preset == PRESET_SCHEDULE:
            return await self._thrm.write_attributes(
                {"operation_preset": 1}, manufacturer=mfg_code
            )
        if preset == PRESET_COMFORT:
            return await self._thrm.write_attributes(
                {"operation_preset": 3}, manufacturer=mfg_code
            )
        if preset == PRESET_ECO:
            return await self._thrm.write_attributes(
                {"operation_preset": 4}, manufacturer=mfg_code
            )
        if preset == PRESET_BOOST:
            return await self._thrm.write_attributes(
                {"operation_preset": 5}, manufacturer=mfg_code
            )
        if preset == PRESET_COMPLEX:
            return await self._thrm.write_attributes(
                {"operation_preset": 6}, manufacturer=mfg_code
            )

        return False


@STRICT_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    manufacturers={
        "_TZE200_b6wax7g0",
    },
)
class BecaThermostat(Thermostat):
    """Beca Thermostat implementation."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._presets = [
            PRESET_NONE,
            PRESET_AWAY,
            PRESET_SCHEDULE,
            PRESET_ECO,
            PRESET_BOOST,
            PRESET_TEMP_MANUAL,
        ]
        self._supported_flags |= ClimateEntityFeature.PRESET_MODE

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return only the heat mode, because the device can't be turned off."""
        return [HVACMode.HEAT]

    async def async_attribute_updated(self, record):
        """Handle attribute update from device."""
        if record.attr_name == "operation_preset":
            if record.value == 0:
                self._preset = PRESET_AWAY
            if record.value == 1:
                self._preset = PRESET_SCHEDULE
            if record.value == 2:
                self._preset = PRESET_NONE
            if record.value == 4:
                self._preset = PRESET_ECO
            if record.value == 5:
                self._preset = PRESET_BOOST
            if record.value == 7:
                self._preset = PRESET_TEMP_MANUAL
        await super().async_attribute_updated(record)

    async def async_preset_handler(self, preset: str, enable: bool = False) -> bool:
        """Set the preset mode."""
        mfg_code = self._zha_device.manufacturer_code
        if not enable:
            return await self._thrm.write_attributes(
                {"operation_preset": 2}, manufacturer=mfg_code
            )
        if preset == PRESET_AWAY:
            return await self._thrm.write_attributes(
                {"operation_preset": 0}, manufacturer=mfg_code
            )
        if preset == PRESET_SCHEDULE:
            return await self._thrm.write_attributes(
                {"operation_preset": 1}, manufacturer=mfg_code
            )
        if preset == PRESET_ECO:
            return await self._thrm.write_attributes(
                {"operation_preset": 4}, manufacturer=mfg_code
            )
        if preset == PRESET_BOOST:
            return await self._thrm.write_attributes(
                {"operation_preset": 5}, manufacturer=mfg_code
            )
        if preset == PRESET_TEMP_MANUAL:
            return await self._thrm.write_attributes(
                {"operation_preset": 7}, manufacturer=mfg_code
            )

        return False


@MULTI_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    manufacturers="Stelpro",
    models={"SORB"},
    stop_on_match_group=CHANNEL_THERMOSTAT,
)
class StelproFanHeater(Thermostat):
    """Stelpro Fan Heater implementation."""

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return only the heat mode, because the device can't be turned off."""
        return [HVACMode.HEAT]


@STRICT_MATCH(
    channel_names=CHANNEL_THERMOSTAT,
    manufacturers={
        "_TZE200_e9ba97vf",  # TV01-ZG
        "_TZE200_husqqvux",  # TSL-TRV-TV01ZG
        "_TZE200_hue3yfsn",  # TV02-ZG
        "_TZE200_kly8gjlz",  # TV05-ZG
    },
)
class ZONNSMARTThermostat(Thermostat):
    """
    ZONNSMART Thermostat implementation.

    Notice that this device uses two holiday presets (2: HolidayMode,
    3: HolidayModeTemp), but only one of them can be set.
    """

    PRESET_HOLIDAY = "holiday"
    PRESET_FROST = "frost protect"

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize ZHA Thermostat instance."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._presets = [
            PRESET_NONE,
            self.PRESET_HOLIDAY,
            PRESET_SCHEDULE,
            self.PRESET_FROST,
        ]
        self._supported_flags |= ClimateEntityFeature.PRESET_MODE

    async def async_attribute_updated(self, record):
        """Handle attribute update from device."""
        if record.attr_name == "operation_preset":
            if record.value == 0:
                self._preset = PRESET_SCHEDULE
            if record.value == 1:
                self._preset = PRESET_NONE
            if record.value == 2:
                self._preset = self.PRESET_HOLIDAY
            if record.value == 3:
                self._preset = self.PRESET_HOLIDAY
            if record.value == 4:
                self._preset = self.PRESET_FROST
        await super().async_attribute_updated(record)

    async def async_preset_handler(self, preset: str, enable: bool = False) -> bool:
        """Set the preset mode."""
        mfg_code = self._zha_device.manufacturer_code
        if not enable:
            return await self._thrm.write_attributes(
                {"operation_preset": 1}, manufacturer=mfg_code
            )
        if preset == PRESET_SCHEDULE:
            return await self._thrm.write_attributes(
                {"operation_preset": 0}, manufacturer=mfg_code
            )
        if preset == self.PRESET_HOLIDAY:
            return await self._thrm.write_attributes(
                {"operation_preset": 3}, manufacturer=mfg_code
            )
        if preset == self.PRESET_FROST:
            return await self._thrm.write_attributes(
                {"operation_preset": 4}, manufacturer=mfg_code
            )
        return False
