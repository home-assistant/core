"""Support for LCN climate control."""

from collections.abc import Iterable
from datetime import timedelta
from functools import partial
from typing import Any, cast

import pypck

from homeassistant.components.climate import (
    DOMAIN as DOMAIN_CLIMATE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_SOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DOMAIN_DATA,
    CONF_LOCKABLE,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SETPOINT,
    CONF_TARGET_VALUE_LOCKED,
)
from .entity import LcnEntity
from .helpers import InputType, LcnConfigEntry

PARALLEL_UPDATES = 2
SCAN_INTERVAL = timedelta(minutes=1)


def add_lcn_entities(
    config_entry: LcnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entity_configs: Iterable[ConfigType],
) -> None:
    """Add entities for this domain."""
    entities = [
        LcnClimate(entity_config, config_entry) for entity_config in entity_configs
    ]

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LcnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LCN switch entities from a config entry."""
    add_entities = partial(
        add_lcn_entities,
        config_entry,
        async_add_entities,
    )

    config_entry.runtime_data.add_entities_callbacks.update(
        {DOMAIN_CLIMATE: add_entities}
    )

    add_entities(
        (
            entity_config
            for entity_config in config_entry.data[CONF_ENTITIES]
            if entity_config[CONF_DOMAIN] == DOMAIN_CLIMATE
        ),
    )


class LcnClimate(LcnEntity, ClimateEntity):
    """Representation of a LCN climate device."""

    def __init__(self, config: ConfigType, config_entry: LcnConfigEntry) -> None:
        """Initialize of a LCN climate device."""
        super().__init__(config, config_entry)

        self.variable = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SOURCE]]
        self.setpoint = pypck.lcn_defs.Var[config[CONF_DOMAIN_DATA][CONF_SETPOINT]]
        self.unit = pypck.lcn_defs.VarUnit.parse(
            config[CONF_DOMAIN_DATA][CONF_UNIT_OF_MEASUREMENT]
        )

        self.regulator_id = pypck.lcn_defs.Var.to_set_point_id(self.setpoint)
        self.is_lockable = config[CONF_DOMAIN_DATA][CONF_LOCKABLE]
        self.target_value_locked = config[CONF_DOMAIN_DATA].get(
            CONF_TARGET_VALUE_LOCKED, -1
        )
        self._max_temp = config[CONF_DOMAIN_DATA][CONF_MAX_TEMP]
        self._min_temp = config[CONF_DOMAIN_DATA][CONF_MIN_TEMP]

        self._is_on = True

        self._attr_hvac_modes = [HVACMode.HEAT]
        if self.is_lockable:
            self._attr_hvac_modes.append(HVACMode.OFF)
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        if len(self.hvac_modes) > 1:
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        # Config schema only allows for: UnitOfTemperature.CELSIUS and UnitOfTemperature.FAHRENHEIT
        if self.unit == pypck.lcn_defs.VarUnit.FAHRENHEIT:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

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
            if not await self.device_connection.lock_regulator(
                self.regulator_id, True, self.target_value_locked
            ):
                return
            self._is_on = False
            self._attr_target_temperature = None
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if not await self.device_connection.var_abs(
            self.setpoint, temperature, self.unit
        ):
            return
        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the state of the entity."""
        self._attr_available = any(
            [
                await self.device_connection.request_status_variable(
                    self.variable, SCAN_INTERVAL.seconds
                ),
                await self.device_connection.request_status_variable(
                    self.setpoint, SCAN_INTERVAL.seconds
                ),
            ]
        )

    def input_received(self, input_obj: InputType) -> None:
        """Set temperature value when LCN input object is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusVar):
            return
        self._attr_available = True
        if input_obj.get_var() == self.variable:
            self._attr_current_temperature = float(
                input_obj.get_value().to_var_unit(self.unit)
            )
        elif input_obj.get_var() == self.setpoint:
            self._is_on = not input_obj.get_value().is_locked_regulator()
            if self._is_on:
                self._attr_target_temperature = float(
                    input_obj.get_value().to_var_unit(self.unit)
                )

        self.async_write_ha_state()
