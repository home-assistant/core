"""Interfaces with Vaillant climate."""

import abc
import logging
from typing import Any, Dict, List, Optional

from pymultimatic.model import (
    ActiveMode,
    Component,
    Mode,
    OperatingModes,
    QuickModes,
    Room,
    System,
    Zone,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .const import DOMAIN as VAILLANT
from .entities import VaillantEntity
from .utils import gen_state_attrs

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Vaillant climate platform."""
    climates = []
    hub = hass.data[VAILLANT].api

    if hub.system:
        if hub.system.zones:
            for zone in hub.system.zones:
                if not zone.rbr:
                    entity = ZoneClimate(hub.system, zone)
                    climates.append(entity)

        if hub.system.rooms:
            for room in hub.system.rooms:
                entity = RoomClimate(hub.system, room)
                climates.append(entity)

    _LOGGER.info("Adding %s climate entities", len(climates))

    async_add_entities(climates, True)
    return True


class VaillantClimate(VaillantEntity, ClimateEntity, abc.ABC):
    """Base class for climate."""

    def __init__(self, system: System, comp_name, comp_id, component: Component):
        """Initialize entity."""
        super().__init__(DOMAIN, None, comp_name, comp_id)
        self._system = None
        self.component = None
        self._refresh(system, component)

    @property
    @abc.abstractmethod
    def active_mode(self) -> ActiveMode:
        """Get active mode of the climate."""

    @property
    def listening(self):
        """Return whether this entity is listening for system changes or not."""
        return True

    @property
    def available(self):
        """Return True if entity is available."""
        return self.component is not None

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        _LOGGER.debug("Target temp is %s", self.active_mode.target)
        return self.active_mode.target

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.component.temperature

    @property
    def is_aux_heat(self) -> Optional[bool]:
        """Return true if aux heater."""
        return False

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

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        return None

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        return None

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""

        hvac_mode = self.mode_to_hvac(self.active_mode.current)

        if hvac_mode is None:
            if self.active_mode.current in [
                OperatingModes.QUICK_VETO,
                OperatingModes.MANUAL,
            ]:
                if self._is_heating():
                    hvac_mode = HVAC_MODE_HEAT
                else:
                    hvac_mode = HVAC_MODE_COOL
            else:
                _LOGGER.warning(
                    "Unknown mode %s, will return None", self.active_mode.current
                )
        return hvac_mode

    async def vaillant_update(self):
        """Update specific for vaillant."""
        self._refresh(self.hub.system, self.hub.find_component(self.component))

    def _refresh(self, system, component):
        """Refresh the entity."""
        self._system = system
        self.component = component

    def _is_heating(self):
        return self.active_mode.target > self.component.temperature

    @abc.abstractmethod
    def mode_to_hvac(self, mode):
        """Get the hvac mode based on vaillant mode."""


class RoomClimate(VaillantClimate):
    """Climate for a room."""

    _MODE_TO_HVAC: Dict[Mode, str] = {
        OperatingModes.AUTO: HVAC_MODE_AUTO,
        OperatingModes.OFF: HVAC_MODE_OFF,
        QuickModes.HOLIDAY: HVAC_MODE_OFF,
        QuickModes.SYSTEM_OFF: HVAC_MODE_OFF,
    }

    _HVAC_TO_MODE: Dict[str, Mode] = {
        HVAC_MODE_AUTO: OperatingModes.AUTO,
        HVAC_MODE_OFF: OperatingModes.OFF,
    }

    _SUPPORTED_HVAC_MODE = list(set(_MODE_TO_HVAC.values()))

    def __init__(self, system: System, room: Room):
        """Initialize entity."""
        super().__init__(system, room.name, room.name, room)

    def mode_to_hvac(self, mode):
        """Get the hvac mode based on vaillant mode."""
        return self._MODE_TO_HVAC.get(mode, None)

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return self._SUPPORTED_HVAC_MODE

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
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return Room.MIN_TARGET_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return Room.MAX_TARGET_TEMP

    @property
    def active_mode(self) -> ActiveMode:
        """Get active mode of the climate."""
        return self._system.get_active_mode_room(self.component)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self.hub.set_room_target_temperature(
            self, float(kwargs.get(ATTR_TEMPERATURE))
        )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        mode = self._HVAC_TO_MODE[hvac_mode]
        await self.hub.set_room_operating_mode(self, self.component, mode)

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        attributes = super().state_attributes
        attributes.update(
            gen_state_attrs(self.component, self.component, self.active_mode)
        )
        return attributes


class ZoneClimate(VaillantClimate):
    """Climate for a zone."""

    _MODE_TO_HVAC: Dict[Mode, str] = {
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
        HVAC_MODE_AUTO: OperatingModes.AUTO,
        HVAC_MODE_OFF: OperatingModes.OFF,
        HVAC_MODE_HEAT: OperatingModes.DAY,
        HVAC_MODE_COOL: OperatingModes.NIGHT,
    }

    _SUPPORTED_HVAC_MODE = list(set(_HVAC_TO_MODE.keys()))

    def __init__(self, system: System, zone: Zone):
        """Initialize entity."""
        super().__init__(system, zone.id, zone.name, zone)

    def mode_to_hvac(self, mode):
        """Get the hvac mode based on vaillant mode."""
        return self._MODE_TO_HVAC.get(mode, None)

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return self._SUPPORTED_HVAC_MODE

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
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return Zone.MIN_TARGET_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return Zone.MAX_TARGET_TEMP

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.active_mode.target

    @property
    def active_mode(self) -> ActiveMode:
        """Get active mode of the climate."""
        return self._system.get_active_mode_zone(self.component)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        if temp and temp != self.active_mode.target:
            _LOGGER.debug("Setting target temp to %s", temp)
            await self.hub.set_zone_target_temperature(self, temp)
        else:
            _LOGGER.debug("Nothing to do")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        mode = self._HVAC_TO_MODE[hvac_mode]
        await self.hub.set_zone_operating_mode(self, mode)

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        attributes = super().state_attributes
        attributes.update(
            gen_state_attrs(self.component, self.component.heating, self.active_mode)
        )
        return attributes
