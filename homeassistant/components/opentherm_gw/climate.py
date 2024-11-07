"""Support for OpenTherm Gateway climate devices."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from types import MappingProxyType
from typing import Any

from pyotgw import vars as gw_vars

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_ID, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OpenThermGatewayHub
from .const import (
    CONF_READ_PRECISION,
    CONF_SET_PRECISION,
    CONF_TEMPORARY_OVRD_MODE,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    THERMOSTAT_DEVICE_DESCRIPTION,
    OpenThermDataSource,
)
from .entity import OpenThermEntityDescription, OpenThermStatusEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_FLOOR_TEMP = False


@dataclass(frozen=True, kw_only=True)
class OpenThermClimateEntityDescription(
    ClimateEntityDescription, OpenThermEntityDescription
):
    """Describes an opentherm_gw climate entity."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an OpenTherm Gateway climate entity."""
    ents = []
    ents.append(
        OpenThermClimate(
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]],
            OpenThermClimateEntityDescription(
                key="thermostat_entity",
                device_description=THERMOSTAT_DEVICE_DESCRIPTION,
            ),
            config_entry.options,
        )
    )

    async_add_entities(ents)


class OpenThermClimate(OpenThermStatusEntity, ClimateEntity):
    """Representation of a climate device."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = []
    _attr_name = None
    _attr_preset_modes = []
    _attr_min_temp = 1
    _attr_max_temp = 30
    _attr_hvac_mode = HVACMode.HEAT
    _away_mode_a: int | None = None
    _away_mode_b: int | None = None
    _away_state_a = False
    _away_state_b = False
    _enable_turn_on_off_backwards_compatibility = False
    _target_temperature: float | None = None
    _new_target_temperature: float | None = None
    entity_description: OpenThermClimateEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermClimateEntityDescription,
        options: MappingProxyType[str, Any],
    ) -> None:
        """Initialize the entity."""
        super().__init__(gw_hub, description)
        if CONF_READ_PRECISION in options:
            self._attr_precision = options[CONF_READ_PRECISION]
        self._attr_target_temperature_step = options.get(CONF_SET_PRECISION)
        self.temporary_ovrd_mode = options.get(CONF_TEMPORARY_OVRD_MODE, True)

    @callback
    def update_options(self, entry):
        """Update climate entity options."""
        self._attr_precision = entry.options[CONF_READ_PRECISION]
        self._attr_target_temperature_step = entry.options[CONF_SET_PRECISION]
        self.temporary_ovrd_mode = entry.options[CONF_TEMPORARY_OVRD_MODE]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Connect to the OpenTherm Gateway device."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._gateway.options_update_signal, self.update_options
            )
        )

    @callback
    def receive_report(self, status: dict[OpenThermDataSource, dict]):
        """Receive and handle a new report from the Gateway."""
        ch_active = status[OpenThermDataSource.BOILER].get(gw_vars.DATA_SLAVE_CH_ACTIVE)
        flame_on = status[OpenThermDataSource.BOILER].get(gw_vars.DATA_SLAVE_FLAME_ON)
        cooling_active = status[OpenThermDataSource.BOILER].get(
            gw_vars.DATA_SLAVE_COOLING_ACTIVE
        )
        if ch_active and flame_on:
            self._attr_hvac_action = HVACAction.HEATING
            self._attr_hvac_mode = HVACMode.HEAT
        elif cooling_active:
            self._attr_hvac_action = HVACAction.COOLING
            self._attr_hvac_mode = HVACMode.COOL
        else:
            self._attr_hvac_action = HVACAction.IDLE

        self._attr_current_temperature = status[OpenThermDataSource.THERMOSTAT].get(
            gw_vars.DATA_ROOM_TEMP
        )
        temp_upd = status[OpenThermDataSource.THERMOSTAT].get(
            gw_vars.DATA_ROOM_SETPOINT
        )

        if self._target_temperature != temp_upd:
            self._new_target_temperature = None
        self._target_temperature = temp_upd

        # GPIO mode 5: 0 == Away
        # GPIO mode 6: 1 == Away
        gpio_a_state = status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_GPIO_A)
        gpio_b_state = status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_GPIO_B)
        self._away_mode_a = gpio_a_state - 5 if gpio_a_state in (5, 6) else None
        self._away_mode_b = gpio_b_state - 5 if gpio_b_state in (5, 6) else None
        self._away_state_a = (
            (
                status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_GPIO_A_STATE)
                == self._away_mode_a
            )
            if self._away_mode_a is not None
            else False
        )
        self._away_state_b = (
            (
                status[OpenThermDataSource.GATEWAY].get(gw_vars.OTGW_GPIO_B_STATE)
                == self._away_mode_b
            )
            if self._away_mode_b is not None
            else False
        )
        self.async_write_ha_state()

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._new_target_temperature or self._target_temperature

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        if self._away_state_a or self._away_state_b:
            return PRESET_AWAY
        return PRESET_NONE

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        _LOGGER.warning("Changing preset mode is not supported")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temp = float(kwargs[ATTR_TEMPERATURE])
            if temp == self.target_temperature:
                return
            self._new_target_temperature = await self._gateway.gateway.set_target_temp(
                temp, self.temporary_ovrd_mode
            )
            self.async_write_ha_state()
