"""Support for the Daikin HVAC."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    PLATFORM_SCHEMA,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as DAIKIN_DOMAIN, DaikinApi
from .const import (
    ATTR_INSIDE_TEMPERATURE,
    ATTR_OUTSIDE_TEMPERATURE,
    ATTR_STATE_OFF,
    ATTR_STATE_ON,
    ATTR_TARGET_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_NAME): cv.string}
)

HA_STATE_TO_DAIKIN = {
    HVACMode.FAN_ONLY: "fan",
    HVACMode.DRY: "dry",
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "hot",
    HVACMode.HEAT_COOL: "auto",
    HVACMode.OFF: "off",
}

DAIKIN_TO_HA_STATE = {
    "fan": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "cool": HVACMode.COOL,
    "hot": HVACMode.HEAT,
    "auto": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
}

HA_STATE_TO_CURRENT_HVAC = {
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.OFF: HVACAction.OFF,
}

HA_PRESET_TO_DAIKIN = {
    PRESET_AWAY: "on",
    PRESET_NONE: "off",
    PRESET_BOOST: "powerful",
    PRESET_ECO: "econo",
}

HA_ATTR_TO_DAIKIN = {
    ATTR_PRESET_MODE: "en_hol",
    ATTR_HVAC_MODE: "mode",
    ATTR_FAN_MODE: "f_rate",
    ATTR_SWING_MODE: "f_dir",
    ATTR_INSIDE_TEMPERATURE: "htemp",
    ATTR_OUTSIDE_TEMPERATURE: "otemp",
    ATTR_TARGET_TEMPERATURE: "stemp",
}

DAIKIN_ATTR_ADVANCED = "adv"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Old way of setting up the Daikin HVAC platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Daikin climate based on config_entry."""
    daikin_api = hass.data[DAIKIN_DOMAIN].get(entry.entry_id)
    async_add_entities([DaikinClimate(daikin_api)], update_before_add=True)


def format_target_temperature(target_temperature):
    """Format target temperature to be sent to the Daikin unit, rounding to nearest half degree."""
    return str(round(float(target_temperature) * 2, 0) / 2).rstrip("0").rstrip(".")


class DaikinClimate(ClimateEntity):
    """Representation of a Daikin HVAC."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, api: DaikinApi) -> None:
        """Initialize the climate device."""

        self._api = api
        self._attr_hvac_modes = list(HA_STATE_TO_DAIKIN)
        self._attr_fan_modes = self._api.device.fan_rate
        self._attr_swing_modes = self._api.device.swing_modes
        self._list = {
            ATTR_HVAC_MODE: self._attr_hvac_modes,
            ATTR_FAN_MODE: self._attr_fan_modes,
            ATTR_SWING_MODE: self._attr_swing_modes,
        }

        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        if (
            self._api.device.support_away_mode
            or self._api.device.support_advanced_modes
        ):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        if self._api.device.support_fan_rate:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if self._api.device.support_swing_mode:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

    async def _set(self, settings):
        """Set device settings using API."""
        values = {}

        for attr in (ATTR_TEMPERATURE, ATTR_FAN_MODE, ATTR_SWING_MODE, ATTR_HVAC_MODE):
            if (value := settings.get(attr)) is None:
                continue

            if (daikin_attr := HA_ATTR_TO_DAIKIN.get(attr)) is not None:
                if attr == ATTR_HVAC_MODE:
                    values[daikin_attr] = HA_STATE_TO_DAIKIN[value]
                elif value in self._list[attr]:
                    values[daikin_attr] = value.lower()
                else:
                    _LOGGER.error("Invalid value %s for %s", attr, value)

            # temperature
            elif attr == ATTR_TEMPERATURE:
                try:
                    values[
                        HA_ATTR_TO_DAIKIN[ATTR_TARGET_TEMPERATURE]
                    ] = format_target_temperature(value)
                except ValueError:
                    _LOGGER.error("Invalid temperature %s", value)

        if values:
            await self._api.device.set(values)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._api.device.mac

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._api.device.inside_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._api.device.target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self._set(kwargs)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current state."""
        ret = HA_STATE_TO_CURRENT_HVAC.get(self.hvac_mode)
        if (
            ret in (HVACAction.COOLING, HVACAction.HEATING)
            and self._api.device.support_compressor_frequency
            and self._api.device.compressor_frequency == 0
        ):
            return HVACAction.IDLE
        return ret

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        daikin_mode = self._api.device.represent(HA_ATTR_TO_DAIKIN[ATTR_HVAC_MODE])[1]
        return DAIKIN_TO_HA_STATE.get(daikin_mode, HVACMode.HEAT_COOL)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        await self._set({ATTR_HVAC_MODE: hvac_mode})

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._api.device.represent(HA_ATTR_TO_DAIKIN[ATTR_FAN_MODE])[1].title()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self._set({ATTR_FAN_MODE: fan_mode})

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self._api.device.represent(HA_ATTR_TO_DAIKIN[ATTR_SWING_MODE])[1].title()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target temperature."""
        await self._set({ATTR_SWING_MODE: swing_mode})

    @property
    def preset_mode(self):
        """Return the preset_mode."""
        if (
            self._api.device.represent(HA_ATTR_TO_DAIKIN[ATTR_PRESET_MODE])[1]
            == HA_PRESET_TO_DAIKIN[PRESET_AWAY]
        ):
            return PRESET_AWAY
        if (
            HA_PRESET_TO_DAIKIN[PRESET_BOOST]
            in self._api.device.represent(DAIKIN_ATTR_ADVANCED)[1]
        ):
            return PRESET_BOOST
        if (
            HA_PRESET_TO_DAIKIN[PRESET_ECO]
            in self._api.device.represent(DAIKIN_ATTR_ADVANCED)[1]
        ):
            return PRESET_ECO
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode == PRESET_AWAY:
            await self._api.device.set_holiday(ATTR_STATE_ON)
        elif preset_mode == PRESET_BOOST:
            await self._api.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_BOOST], ATTR_STATE_ON
            )
        elif preset_mode == PRESET_ECO:
            await self._api.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_ECO], ATTR_STATE_ON
            )
        elif self.preset_mode == PRESET_AWAY:
            await self._api.device.set_holiday(ATTR_STATE_OFF)
        elif self.preset_mode == PRESET_BOOST:
            await self._api.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_BOOST], ATTR_STATE_OFF
            )
        elif self.preset_mode == PRESET_ECO:
            await self._api.device.set_advanced_mode(
                HA_PRESET_TO_DAIKIN[PRESET_ECO], ATTR_STATE_OFF
            )

    @property
    def preset_modes(self):
        """List of available preset modes."""
        ret = [PRESET_NONE]
        if self._api.device.support_away_mode:
            ret.append(PRESET_AWAY)
        if self._api.device.support_advanced_modes:
            ret += [PRESET_ECO, PRESET_BOOST]
        return ret

    async def async_update(self) -> None:
        """Retrieve latest state."""
        await self._api.async_update()

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self._api.device.set({})

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self._api.device.set(
            {HA_ATTR_TO_DAIKIN[ATTR_HVAC_MODE]: HA_STATE_TO_DAIKIN[HVACMode.OFF]}
        )

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info
