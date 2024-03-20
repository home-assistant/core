"""Support for LCN climate control."""

from __future__ import annotations

from typing import Any, cast

import pypck

from homeassistant.components.climate import (
    DOMAIN as DOMAIN_CLIMATE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_SOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import LcnEntity
from .const import (
    CONF_DOMAIN_DATA,
    CONF_LOCKABLE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SETPOINT,
)
from .helpers import DeviceConnectionType, InputType, get_device_connection

PARALLEL_UPDATES = 0


def create_lcn_climate_entity(
    hass: HomeAssistant, entity_config: ConfigType, config_entry: ConfigEntry
) -> LcnEntity:
    """Set up an entity for this domain."""
    device_connection = get_device_connection(
        hass, entity_config[CONF_ADDRESS], config_entry
    )

    return LcnClimate(entity_config, config_entry.entry_id, device_connection)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""

    async_add_entities(
        create_lcn_climate_entity(hass, entity_config, config_entry)
        for entity_config in config_entry.data[CONF_ENTITIES]
        if entity_config[CONF_DOMAIN] == DOMAIN_CLIMATE
    )


class LcnClimate(LcnEntity, ClimateEntity):
    """Representation of a LCN climate device."""

    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, config: ConfigType, entry_id: str, device_connection: DeviceConnectionType
    ) -> None:
        """Initialize of a LCN climate device."""
        super().__init__(config, entry_id, device_connection)

        self.variable = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        self.setpoint = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SETPOINT]]
        self.unit = pypck.lcn_defs.VarUnit.parse(
            config[CONF_DOMAIN_DATA][CONF_UNIT_OF_MEASUREMENT]
        )

        self.regulator_id = pypck.lcn_defs.Var.to_set_point_id(self.setpoint)
        self.is_lockable = config[CONF_DOMAIN_DATA][CONF_LOCKABLE]
        self._max_temp = config[CONF_DOMAIN_DATA][CONF_MAX_TEMP]
        self._min_temp = config[CONF_DOMAIN_DATA][CONF_MIN_TEMP]

        self._current_temperature = None
        self._target_temperature = None
        self._is_on = True

        self._attr_hvac_modes = [HVACMode.HEAT]
        if self.is_lockable:
            self._attr_hvac_modes.append(HVACMode.OFF)
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if len(self.hvac_modes) > 1:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if not self.device_connection.is_group:
            await self.device_connection.activate_status_request_handler(self.variable)
            await self.device_connection.activate_status_request_handler(self.setpoint)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        if not self.device_connection.is_group:
            await self.device_connection.cancel_status_request_handler(self.variable)
            await self.device_connection.cancel_status_request_handler(self.setpoint)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        # Config schema only allows for: UnitOfTemperature.CELSIUS and UnitOfTemperature.FAHRENHEIT
        if self.unit == pypck.lcn_defs.VarUnit.FAHRENHEIT:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._is_on:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return cast(float, self._max_temp)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return cast(float, self._min_temp)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            if not await self.device_connection.lock_regulator(
                self.regulator_id, False
            ):
                return
            self._is_on = True
            self.async_write_ha_state()
        elif hvac_mode == HVACMode.OFF:
            if not await self.device_connection.lock_regulator(self.regulator_id, True):
                return
            self._is_on = False
            self._target_temperature = None
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if not await self.device_connection.var_abs(
            self.setpoint, temperature, self.unit
        ):
            return
        self._target_temperature = temperature
        self.async_write_ha_state()

    def input_received(self, input_obj: InputType) -> None:
        """Set temperature value when LCN input object is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusVar):
            return

        if input_obj.get_var() == self.variable:
            self._current_temperature = input_obj.get_value().to_var_unit(self.unit)
        elif input_obj.get_var() == self.setpoint:
            self._is_on = not input_obj.get_value().is_locked_regulator()
            if self._is_on:
                self._target_temperature = input_obj.get_value().to_var_unit(self.unit)

        self.async_write_ha_state()
