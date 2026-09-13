"""Support for Atlantic Pass APC Heating and Cooling Zone."""

from datetime import timedelta
from typing import Any, cast, override

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.models import Command, Action

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, LOGGER
from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity
from ..executor import OverkizExecutor

OVERKIZ_TO_HVAC_MODE: dict[str, HVACMode] = {
    OverkizCommandParam.STOP: HVACMode.OFF,
    OverkizCommandParam.HEATING: HVACMode.HEAT,
    OverkizCommandParam.COOLING: HVACMode.COOL,
    OverkizCommandParam.INTERNAL_SCHEDULING: HVACMode.AUTO,
    OverkizCommandParam.EXTERNAL_SCHEDULING: HVACMode.AUTO,
    OverkizCommandParam.ABSENCE: HVACMode.AUTO,
    OverkizCommandParam.MANU: HVACMode.AUTO,
    OverkizCommandParam.ECO: HVACMode.AUTO,
    OverkizCommandParam.COMFORT: HVACMode.AUTO,
    OverkizCommandParam.AUTO: HVACMode.AUTO,
}

HVAC_MODE_TO_OVERKIZ: dict[HVACMode, str] = {
    HVACMode.OFF: OverkizCommandParam.STOP,
    HVACMode.HEAT: OverkizCommandParam.HEATING,
    HVACMode.COOL: OverkizCommandParam.COOLING,
    HVACMode.AUTO: OverkizCommandParam.ECO,
}

OVERKIZ_TO_PRESET_MODES: dict[str, str] = {
    OverkizCommandParam.COMFORT: PRESET_COMFORT,
    OverkizCommandParam.ECO: PRESET_ECO,
    OverkizCommandParam.ABSENCE: PRESET_AWAY,

    OverkizCommandParam.DEROGATION: PRESET_AWAY,
    OverkizCommandParam.EXTERNAL_SETPOINT: PRESET_ECO,
    OverkizCommandParam.FROSTPROTECTION: PRESET_AWAY,
    OverkizCommandParam.MANU: PRESET_COMFORT,
    OverkizCommandParam.STOP: PRESET_NONE,
}

PRESET_MODES_TO_OVERKIZ: dict[str, str] = {
    PRESET_COMFORT: OverkizCommandParam.COMFORT,
    PRESET_ECO: OverkizCommandParam.ECO,
    PRESET_AWAY: OverkizCommandParam.ABSENCE,
}


class AtlanticPassAPCHeatingAndCoolingZone(OverkizEntity, ClimateEntity):
    """Representation of Atlantic Pass APC Heating and Cooling Zone Control."""
    LOGGER.debug("OVERKIZCUSTOM: AtlanticPassAPCHeatingAndCoolingZone")

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_preset_modes = [*PRESET_MODES_TO_OVERKIZ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN


    def __init__(self, device_url: str, coordinator: OverkizDataUpdateCoordinator) -> None:
        """Init method."""
        LOGGER.debug("OVERKIZCUSTOM: __init__")

        super().__init__(device_url, coordinator)

        # Temperature sensor use the same base_device_url and use the n+1 index
        self.temperature_device = (
            self.executor.linked_device(subsystem_id + 1)
            if (subsystem_id := self.device.identifier.subsystem_id) is not None
            else None
        )
        
        self.main_device = self.executor.linked_device(1)
        self.main_executor = (OverkizExecutor(self.main_device.device_url, coordinator)
            if self.main_device is not None
            else self.executor
        )
        self.client = coordinator.client

        


    @property
    @override
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        LOGGER.debug("OVERKIZCUSTOM: current_temperature")

        res = None

        if self.temperature_device is not None:
           res = cast(float, self.temperature_device.states.get(OverkizState.CORE_TEMPERATURE).value)

        LOGGER.debug("OVERKIZCUSTOM: current_temperature res=%s", res)
        return res

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Return the HVAC mode exposed by this zone entity."""
        LOGGER.debug("OVERKIZCUSTOM: hvac_mode")

        current_mode = self.current_operating_mode
        if current_mode == HVACMode.COOL:
            res = OVERKIZ_TO_HVAC_MODE[self.current_cooling_profile]
        elif current_mode == HVACMode.HEAT:
            res = OVERKIZ_TO_HVAC_MODE[self.current_heating_profile]
        else:
            res = current_mode

        LOGGER.debug("OVERKIZCUSTOM: hvac_mode res=%s", res)
        return res

    @property
    def current_operating_mode(self) -> HVACMode:
        """Return the actual heating or cooling mode from the main device."""
        LOGGER.debug("OVERKIZCUSTOM: current_operating_mode")

        operating_mode = OVERKIZ_TO_HVAC_MODE.get(cast(str, self.main_device.states.get_value(OverkizState.IO_PASS_APC_OPERATING_MODE)))
        
        LOGGER.debug("OVERKIZCUSTOM: current_operating_mode res=%s", operating_mode)
        return operating_mode

    @property
    def current_heating_profile(self) -> str:
        """Return current heating profile."""
        LOGGER.debug("OVERKIZCUSTOM: current_heating_profile")

        res = cast(str, self.device.states.get_value(OverkizState.IO_PASS_APC_HEATING_PROFILE),)

        LOGGER.debug("OVERKIZCUSTOM: current_heating_profile res=%s", res)
        return res

    @property
    def current_cooling_profile(self) -> str:
        """Return current cooling profile."""
        LOGGER.debug("OVERKIZCUSTOM: current_cooling_profile")

        res = cast(str, self.device.states.get_value(OverkizState.IO_PASS_APC_COOLING_PROFILE),) 

        LOGGER.debug("OVERKIZCUSTOM: current_cooling_profile res=%s", res)
        return res


    async def async_cancel_absence(self) -> None:
        LOGGER.debug("OVERKIZCUSTOM: async_cancel_absence")

        
        zero_date = {
            "month": 0,
            "hour": 0,
            "year": 0,
            "day": 0,
            "minute": 0,
        }

        commands = []

        commands.append(Command(name=OverkizCommand.SET_ABSENCE_START_DATE_TIME, parameters=[zero_date]))
        commands.append(Command(name=OverkizCommand.SET_ABSENCE_END_DATE_TIME, parameters=[zero_date]))
        commands.append(Command(name=OverkizCommand.CANCEL_ABSENCE))


        commands.append(Command(name=OverkizCommand.REFRESH_ZONES_PASS_APC_COOLING_PROFILE))                
        commands.append(Command(name=OverkizCommand.REFRESH_ZONES_PASS_APC_HEATING_PROFILE))
        commands.append(Command(name=OverkizCommand.REFRESH_ZONES_TARGET_TEMPERATURE))

        
        await self.main_executor.async_execute_commands(commands)           
       
    
    async def async_set_absence_mode(self) -> None:
        """Start absence mode on the main APC device."""
        LOGGER.debug("OVERKIZCUSTOM: async_set_absence_mode")

        now = dt_util.now()
        start_date = {
            "month": now.month,
            "hour": now.hour,
            "year": now.year,
            "day": now.day,
            "minute": now.minute,
        }
        end = now + timedelta(days=365)
        end_date = {
            "month": end.month,
            "hour": end.hour,
            "year": end.year,
            "day": end.day,
            "minute": end.minute
        }
        
        commands = []


        commands.append(Command(name=OverkizCommand.SET_ABSENCE_START_DATE_TIME, parameters=[start_date]))
        commands.append(Command(name=OverkizCommand.SET_ABSENCE_END_DATE_TIME, parameters=[end_date]))

        current_operating_mode = self.current_operating_mode
        if current_operating_mode == HVACMode.COOL:
            commands.append(Command(name=OverkizCommand.REFRESH_ZONES_PASS_APC_COOLING_PROFILE))                
        elif current_operating_mode == HVACMode.HEAT:
            commands.append(Command(name=OverkizCommand.REFRESH_ZONES_PASS_APC_HEATING_PROFILE))

        commands.append(Command(name=OverkizCommand.REFRESH_ZONES_TARGET_TEMPERATURE))
        await self.main_executor.async_execute_commands(commands)




    def is_absence_mode(self) -> bool:
        LOGGER.debug("OVERKIZCUSTOM: is_absence_mode")
        
        absence_status = self.main_device.states.get_value(OverkizState.CORE_ABSENCE_END_DATE_TIME)
        res = self.main_device.states.get_value(OverkizState.CORE_ABSENCE_END_DATE_TIME) is not None
        
        LOGGER.debug("OVERKIZCUSTOM: is_absence_mode absence_status=%s, res=%s", absence_status, res)
        return res
    
    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        LOGGER.debug("OVERKIZCUSTOM: async_set_preset_mode preset_mode=%s", preset_mode)

        if preset_mode == PRESET_AWAY:
            await self.async_set_absence_mode()
        elif self.is_absence_mode():
            await self.async_cancel_absence()
        
        if self.current_operating_mode == HVACMode.COOL:
            await self.async_set_cooling_mode(PRESET_MODES_TO_OVERKIZ[preset_mode])
        elif self.current_operating_mode == HVACMode.HEAT:
            await self.async_set_heating_mode(PRESET_MODES_TO_OVERKIZ[preset_mode])

    async def async_set_heating_mode(self, mode: str) -> None:
        """Set new heating mode and refresh states."""
        LOGGER.debug("OVERKIZCUSTOM: async_set_heating_mode mode=%s", mode)

        commands = []

        if mode==OverkizCommandParam.STOP:
            commands.append(Command(name=OverkizCommand.SET_HEATING_ON_OFF, parameters=[OverkizCommandParam.OFF]))
            commands.append(Command(name=OverkizCommand.SET_COOLING_ON_OFF, parameters=[OverkizCommandParam.ON]))
        else: #AUTO
            commands.append(Command(name=OverkizCommand.SET_HEATING_ON_OFF, parameters=[OverkizCommandParam.ON]))
            commands.append(Command(name=OverkizCommand.SET_PASS_APC_COOLING_MODE, parameters=[OverkizCommandParam.STOP]))        
            commands.append(Command(name=OverkizCommand.REFRESH_PASS_APC_COOLING_PROFILE))        
            commands.append(Command(name=OverkizCommand.SET_COOLING_ON_OFF, parameters=[OverkizCommandParam.OFF])) 

        commands.append(Command(name=OverkizCommand.SET_PASS_APC_HEATING_MODE, parameters=[mode]))
        commands.append(Command(name=OverkizCommand.REFRESH_PASS_APC_COOLING_MODE))        
        commands.append(Command(name=OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE))        
        commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE)) 

        await self.executor.async_execute_commands(commands)


    async def async_set_cooling_mode(self, mode: str) -> None:
        """Set new cooling mode and refresh states."""
        LOGGER.debug("OVERKIZCUSTOM: async_set_cooling_mode mode=%s", mode)

        commands = []

        if mode==OverkizCommandParam.STOP:
            commands.append(Command(name=OverkizCommand.SET_COOLING_ON_OFF, parameters=[OverkizCommandParam.OFF]))
            commands.append(Command(name=OverkizCommand.SET_HEATING_ON_OFF, parameters=[OverkizCommandParam.ON]))
        else: #AUTO
            commands.append(Command(name=OverkizCommand.SET_COOLING_ON_OFF, parameters=[OverkizCommandParam.ON]))
            commands.append(Command(name=OverkizCommand.SET_PASS_APC_HEATING_MODE, parameters=[OverkizCommandParam.STOP]))        
            commands.append(Command(name=OverkizCommand.REFRESH_PASS_APC_HEATING_PROFILE))        
            commands.append(Command(name=OverkizCommand.SET_HEATING_ON_OFF, parameters=[OverkizCommandParam.OFF])) 

        commands.append(Command(name=OverkizCommand.SET_PASS_APC_COOLING_MODE, parameters=[mode]))
        commands.append(Command(name=OverkizCommand.REFRESH_PASS_APC_COOLING_MODE))        
        commands.append(Command(name=OverkizCommand.REFRESH_PASS_APC_COOLING_PROFILE))        
        commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE)) 

        await self.executor.async_execute_commands(commands)



    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the zone HVAC mode."""
        LOGGER.debug("OVERKIZCUSTOM: async_set_hvac_mode hvac_mode=%s",hvac_mode)

        operating_mode = self.current_operating_mode

        if operating_mode == HVACMode.COOL:
            await self.async_set_cooling_mode(HVAC_MODE_TO_OVERKIZ[hvac_mode])
        elif operating_mode == HVACMode.HEAT:
            await self.async_set_heating_mode(HVAC_MODE_TO_OVERKIZ[hvac_mode])

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the active mode for this zone."""
        LOGGER.debug("OVERKIZCUSTOM: async_turn_off")

        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        LOGGER.debug("OVERKIZCUSTOM: preset_mode")

        current_operating_mode = self.current_operating_mode

        if current_operating_mode == HVACMode.COOL:
            res =  OVERKIZ_TO_PRESET_MODES.get(cast(str,self.device.states.get_value(OverkizState.IO_PASS_APC_COOLING_PROFILE)))
        elif current_operating_mode == HVACMode.HEAT:
            res =  OVERKIZ_TO_PRESET_MODES.get(cast(str,self.device.states.get_value(OverkizState.IO_PASS_APC_HEATING_PROFILE)))
        else:
            res = PRESET_NONE

        LOGGER.debug("OVERKIZCUSTOM: preset_mode res=%s", res) 
        return res

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return hvac target temperature."""
        LOGGER.debug("OVERKIZCUSTOM: target_temperature")

        if self.hvac_mode == HVACMode.OFF:
            res = None
        else:
            res = cast(float, self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE))

        LOGGER.debug("OVERKIZCUSTOM: target_temperature res=%s", res)
        return res

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new temperature."""
        LOGGER.debug("OVERKIZCUSTOM: async_set_temperature")

        commands = []
        commands_main = []

     
        temperature = kwargs[ATTR_TEMPERATURE]
        current_operating_mode = self.current_operating_mode

        if current_operating_mode == HVACMode.COOL:

            profile = self.current_cooling_profile
            
            if profile == OverkizCommandParam.ECO:
                other_profile_temperature = cast(float | None, self.device.states.get_value(OverkizState.CORE_COMFORT_COOLING_TARGET_TEMPERATURE))
                if temperature <= other_profile_temperature:
                    #cambiar temperatura comfort primero 
                    commands.append(Command(name=OverkizCommand.SET_COMFORT_COOLING_TARGET_TEMPERATURE,parameters=[temperature-0.5]))
                    commands.append(Command(name=OverkizCommand.REFRESH_COMFORT_COOLING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.SET_ECO_COOLING_TARGET_TEMPERATURE,parameters=[temperature]))
                commands.append(Command(name=OverkizCommand.REFRESH_ECO_COOLING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))

            elif profile == OverkizCommandParam.COMFORT:
                other_profile_temperature = cast(float | None, self.device.states.get_value(OverkizState.CORE_ECO_COOLING_TARGET_TEMPERATURE))
                if temperature >= other_profile_temperature:
                    #cambiar temperatura eco primero
                    commands.append(Command(name=OverkizCommand.SET_ECO_COOLING_TARGET_TEMPERATURE,parameters=[temperature+0.5]))
                    commands.append(Command(name=OverkizCommand.REFRESH_ECO_COOLING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.SET_COMFORT_COOLING_TARGET_TEMPERATURE,parameters=[temperature]))
                commands.append(Command(name=OverkizCommand.REFRESH_COMFORT_COOLING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))
            elif profile == OverkizCommandParam.ABSENCE:
                temperature = max(18, min(40, temperature))
                commands_main.append(Command(name=OverkizCommand.SET_ABSENCE_COOLING_TARGET_TEMPERATURE,parameters=[temperature]))
                commands_main.append(Command(name=OverkizCommand.REFRESH_ZONES_TARGET_TEMPERATURE))
            

        elif current_operating_mode == HVACMode.HEAT:
            profile = self.current_heating_profile
            if profile == OverkizCommandParam.ECO:
                other_profile_temperature = cast(float | None, self.device.states.get_value(OverkizState.CORE_COMFORT_HEATING_TARGET_TEMPERATURE))
                if temperature >= other_profile_temperature:
                    #cambiar temperatura confort primero
                    commands.append(Command(name=OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE,parameters=[temperature+0.5]))
                    commands.append(Command(name=OverkizCommand.REFRESH_COMFORT_HEATING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.SET_ECO_HEATING_TARGET_TEMPERATURE,parameters=[temperature]))
                commands.append(Command(name=OverkizCommand.REFRESH_ECO_HEATING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))
            elif profile == OverkizCommandParam.COMFORT:
                other_profile_temperature = cast(float | None, self.device.states.get_value(OverkizState.CORE_ECO_HEATING_TARGET_TEMPERATURE))
                if temperature <= other_profile_temperature:
                    #cambiar temperatura eco primero
                    commands.append(Command(name=OverkizCommand.SET_ECO_HEATING_TARGET_TEMPERATURE,parameters=[temperature-0.5]))
                    commands.append(Command(name=OverkizCommand.REFRESH_ECO_HEATING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.SET_COMFORT_HEATING_TARGET_TEMPERATURE,parameters=[temperature]))
                commands.append(Command(name=OverkizCommand.REFRESH_COMFORT_HEATING_TARGET_TEMPERATURE))
                commands.append(Command(name=OverkizCommand.REFRESH_TARGET_TEMPERATURE))
            elif profile == OverkizCommandParam.ABSENCE:
                temperature = max(4, min(16, temperature))
                commands_main.append(Command(name=OverkizCommand.SET_ABSENCE_HEATING_TARGET_TEMPERATURE,parameters=[temperature]))
                commands_main.append(Command(name=OverkizCommand.REFRESH_ZONES_TARGET_TEMPERATURE))
            
        
        if commands:
            await self.executor.async_execute_commands(commands)
        elif commands_main:
            await self.main_executor.async_execute_commands(commands_main)


