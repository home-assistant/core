"""Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/zha.climate/
"""

from __future__ import annotations

import functools
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.CLIMATE]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Thermostat, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class Thermostat(ZHAEntity, ClimateEntity):
    """Representation of a ZHA Thermostat device."""

    _attr_precision = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key: str = "thermostat"
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.entity_data.entity.current_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return current FAN mode."""
        return self.entity_data.entity.fan_mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return supported FAN modes."""
        return self.entity_data.entity.fan_modes

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        if self.entity_data.entity.hvac_action is None:
            return None
        return HVACAction(self.entity_data.entity.hvac_action)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return HVAC operation mode."""
        if self.entity_data.entity.hvac_mode is None:
            return None
        return HVACMode(self.entity_data.entity.hvac_mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC operation modes."""
        return [HVACMode(mode) for mode in self.entity_data.entity.hvac_modes]

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        return self.entity_data.entity.preset_mode

    @property
    def preset_modes(self) -> list[str] | None:
        """Return supported preset modes."""
        return self.entity_data.entity.preset_modes

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return ClimateEntityFeature(self.entity_data.entity.supported_features.value)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.entity_data.entity.target_temperature

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound temperature we try to reach."""
        return self.entity_data.entity.target_temperature_high

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound temperature we try to reach."""
        return self.entity_data.entity.target_temperature_low

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.entity_data.entity.max_temp

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.entity_data.entity.min_temp

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.entity_data.entity.async_set_fan_mode(fan_mode=fan_mode)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.entity_data.entity.async_set_hvac_mode(hvac_mode=hvac_mode)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.entity_data.entity.async_set_preset_mode(preset_mode=preset_mode)
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.entity_data.entity.async_set_temperature(
            target_temp_low=kwargs.get(ATTR_TARGET_TEMP_LOW),
            target_temp_high=kwargs.get(ATTR_TARGET_TEMP_HIGH),
            temperature=kwargs.get(ATTR_TEMPERATURE),
            hvac_mode=kwargs.get(ATTR_HVAC_MODE),
        )
        self.async_write_ha_state()
