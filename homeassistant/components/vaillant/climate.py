"""Interfaces with Vaillant climate."""

import abc
import logging
from typing import Optional, List, Dict, Any
from datetime import timedelta, datetime

from pymultimatic.model import (
    System,
    Room,
    Component,
    Zone,
    OperatingModes,
    QuickModes,
    Mode)

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE,
    DOMAIN,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    PRESET_AWAY,
    HVAC_MODE_FAN_ONLY,
    PRESET_COMFORT,
    PRESET_BOOST,
    PRESET_SLEEP,
    PRESET_HOME,
    HVAC_MODE_COOL,
)
from homeassistant.util import dt as dt_util
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

from . import HUB, BaseVaillantEntity, CONF_ROOM_CLIMATE, CONF_ZONE_CLIMATE, \
    ATTR_VAILLANT_MODE, ATTR_QUICK_VETO_END, ATTR_VAILLANT_SUB_MODE, \
    ATTR_VAILLANT_NEXT_SUB_MODE, ATTR_VAILLANT_SUB_MODE_END

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Vaillant climate platform."""
    climates = []
    hub = hass.data[HUB]

    if hub.system:
        if hub.system.zones and hub.config[CONF_ZONE_CLIMATE]:
            for zone in hub.system.zones:
                if not zone.rbr:
                    entity = VaillantZoneClimate(hub.system, zone)
                    hub.add_listener(entity)
                    climates.append(entity)

        if hub.system.rooms and hub.config[CONF_ROOM_CLIMATE]:
            for room in hub.system.rooms:
                entity = VaillantRoomClimate(hub.system, room)
                hub.add_listener(entity)
                climates.append(entity)

    _LOGGER.info("Adding %s climate entities", len(climates))

    async_add_entities(climates, True)
    return True


class VaillantClimate(BaseVaillantEntity, ClimateDevice, abc.ABC):
    """Base class for climate."""

    def __init__(self, system: System, comp_name, comp_id,
                 component: Component):
        """Initialize entity."""
        super().__init__(DOMAIN, None, comp_name, comp_id)
        self._system = None
        self._component = None
        self._active_mode = None
        self._refresh(system, component)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._component is not None

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.debug("Target temp is %s", self._active_mode.target_temperature)
        return self._active_mode.target_temperature

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._component.current_temperature

    @property
    def is_aux_heat(self) -> Optional[bool]:
        """Return true if aux heater."""
        return False

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        attributes = super().state_attributes
        attributes.update({
            ATTR_VAILLANT_MODE: self._active_mode.current_mode.name
        })

        if self._active_mode.current_mode == OperatingModes.QUICK_VETO:
            if self._component.quick_veto.remaining_duration:
                qveto_millis = \
                    self._component.quick_veto.remaining_duration \
                    * 60 * 1000
                end_time = dt_util.utcnow() \
                    + timedelta(milliseconds=qveto_millis)
                attributes.update({
                    ATTR_QUICK_VETO_END: end_time.isoformat()
                })
        elif self._active_mode.current_mode == OperatingModes.AUTO:
            now = datetime.now()
            abs_min = now.hour * 60 + now.minute
            next_setting = self._component.time_program.get_next(now)

            next_start = now
            # it means, next setting is tomorrow
            if next_setting.absolute_minutes < abs_min:
                next_start = next_start + timedelta(days=1)
            next_start.replace(hour=next_setting.hour,
                               minute=next_setting.minute)
            next_start = dt_util.as_utc(next_start)

            attributes.update({
                ATTR_VAILLANT_SUB_MODE: self._active_mode.sub_mode.name,
                ATTR_VAILLANT_NEXT_SUB_MODE:
                    next_setting.setting.name if next_setting.setting else
                    next_setting.temperature,
                ATTR_VAILLANT_SUB_MODE_END: next_start.isoformat()
            })

        return attributes

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return None

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return None

    @property
    def swing_mode(self) -> Optional[str]:
        """Return the swing setting."""
        return None

    @property
    def swing_modes(self) -> Optional[List[str]]:
        """Return the list of available swing modes."""
        return None

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        pass

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        pass

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        pass

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        pass

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        pass

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._refresh(
            self.hub.system, self.hub.find_component(self._component))

    def _refresh(self, system, component):
        """Refresh the entity."""
        self._system = system
        self._component = component
        self._active_mode = self.get_active_mode()

    @abc.abstractmethod
    def get_active_mode(self):
        """Get active mode of the climate."""
        pass


class VaillantRoomClimate(VaillantClimate):
    """Climate for a room."""

    _MODE_TO_PRESET: Dict[Mode, str] = {
        OperatingModes.QUICK_VETO: PRESET_BOOST,
        OperatingModes.AUTO: PRESET_COMFORT,
        OperatingModes.ON: PRESET_HOME,
        OperatingModes.OFF: PRESET_SLEEP,
        OperatingModes.MANUAL: PRESET_COMFORT,
        QuickModes.HOLIDAY: PRESET_AWAY,
        QuickModes.SYSTEM_OFF: PRESET_SLEEP,
    }

    _MODE_TO_HVAC: Dict[Mode, str] = {
        OperatingModes.QUICK_VETO: HVAC_MODE_HEAT,
        OperatingModes.MANUAL: HVAC_MODE_HEAT,
        OperatingModes.AUTO: HVAC_MODE_AUTO,
        OperatingModes.OFF: HVAC_MODE_OFF,
        QuickModes.HOLIDAY: HVAC_MODE_OFF,
        QuickModes.SYSTEM_OFF: HVAC_MODE_OFF,
    }

    _HVAC_TO_MODE: Dict[str, Mode] = {
        HVAC_MODE_AUTO: OperatingModes.AUTO,
        HVAC_MODE_OFF: OperatingModes.OFF,
        HVAC_MODE_HEAT: OperatingModes.MANUAL,
    }

    _SUPPORTED_HVAC_MODE = list(set(_MODE_TO_HVAC.values()))

    def __init__(self, system: System, room: Room):
        """Initialize entity."""
        super().__init__(system, room.name, room.name, room)

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return self._MODE_TO_HVAC[self._active_mode.current_mode]

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        if self._active_mode.current_mode != QuickModes.HOLIDAY:
            return self._SUPPORTED_HVAC_MODE
        return []

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._active_mode.current_mode != QuickModes.HOLIDAY:
            return SUPPORT_TARGET_TEMPERATURE
        return 0

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return Room.MIN_TARGET_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return Room.MAX_TARGET_TEMP

    def get_active_mode(self):
        """Get active mode of the climate."""
        return self._system.get_active_mode_room(self._component)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        self.hub.set_room_target_temperature(
            self, self._component, float(kwargs.get(ATTR_TEMPERATURE)))

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        mode = self._HVAC_TO_MODE[hvac_mode]
        self.hub.set_room_operating_mode(self, self._component, mode)

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return None


class VaillantZoneClimate(VaillantClimate):
    """Climate for a zone."""

    _MODE_TO_HVAC: Dict[Mode, str] = {
        OperatingModes.QUICK_VETO: HVAC_MODE_HEAT,
        OperatingModes.DAY: HVAC_MODE_HEAT,
        QuickModes.PARTY: HVAC_MODE_HEAT,
        OperatingModes.NIGHT: HVAC_MODE_COOL,
        OperatingModes.AUTO: HVAC_MODE_AUTO,
        QuickModes.ONE_DAY_AT_HOME: HVAC_MODE_AUTO,
        OperatingModes.OFF: HVAC_MODE_OFF,
        QuickModes.ONE_DAY_AWAY: HVAC_MODE_OFF,
        QuickModes.HOLIDAY: HVAC_MODE_OFF,
        QuickModes.SYSTEM_OFF: HVAC_MODE_OFF,
        QuickModes.VENTILATION_BOOST: HVAC_MODE_FAN_ONLY,
    }

    _HVAC_TO_MODE: Dict[str, Mode] = {
        HVAC_MODE_COOL: OperatingModes.NIGHT,
        HVAC_MODE_AUTO: OperatingModes.AUTO,
        HVAC_MODE_OFF: OperatingModes.OFF,
        HVAC_MODE_HEAT: OperatingModes.DAY
    }

    _SUPPORTED_HVAC_MODE = list(set(_HVAC_TO_MODE.keys()))

    def __init__(self, system: System, zone: Zone):
        """Initialize entity."""
        super().__init__(system, zone.id, zone.name, zone)

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return self._MODE_TO_HVAC[self._active_mode.current_mode]

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        if self._active_mode.current_mode != QuickModes.HOLIDAY:
            return self._SUPPORTED_HVAC_MODE
        return []

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return None

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._active_mode.current_mode != QuickModes.HOLIDAY:
            if self._active_mode.current_mode == OperatingModes.AUTO:
                return SUPPORT_TARGET_TEMPERATURE_RANGE
            return SUPPORT_TARGET_TEMPERATURE
        return 0

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return Zone.MIN_TARGET_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return Zone.MAX_TARGET_TEMP

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        _LOGGER.debug("Target high temp is %s",
                      self._component.target_temperature)
        return self._active_mode.target_temperature

    @property
    def target_temperature_low(self):
        """Return the highbound target temperature we try to reach."""
        _LOGGER.debug("Target low temp is %s",
                      self._component.target_min_temperature)
        # if self._active_mode.target_temperature == Zone.MIN_TARGET_TEMP:
        #     return self._active_mode.target_temperature
        return self._component.target_min_temperature

    def get_active_mode(self):
        """Get active mode of the climate."""
        return self._system.get_active_mode_zone(self._component)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)

        if temp and temp != self._active_mode.target_temperature:
            _LOGGER.debug("Setting target temp to %s", temp)
            self.hub.set_zone_target_temperature(self, self._component, temp)
        elif low_temp and low_temp != self._component.target_min_temperature:
            _LOGGER.debug("Setting target low temp to %s", low_temp)
            self.hub.set_zone_target_low_temperature(self, self._component,
                                                     low_temp)
        elif high_temp and high_temp != self._component.target_temperature:
            _LOGGER.debug("Setting target high temp to %s", high_temp)
            self.hub.set_zone_target_high_temperature(self, self._component,
                                                      high_temp)
        else:
            _LOGGER.debug("Nothing to do")

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        mode = self._HVAC_TO_MODE[hvac_mode]
        self.hub.set_zone_operating_mode(self, self._component, mode)
