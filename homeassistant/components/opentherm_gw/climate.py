"""Support for OpenTherm Gateway climate devices."""

from __future__ import annotations

import logging
from typing import Any

from pyotgw import vars as gw_vars

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ID,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import (
    CONF_FLOOR_TEMP,
    CONF_READ_PRECISION,
    CONF_SET_PRECISION,
    CONF_TEMPORARY_OVRD_MODE,
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_FLOOR_TEMP = False


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
            config_entry.options,
        )
    )

    async_add_entities(ents)


class OpenThermClimate(ClimateEntity):
    """Representation of a climate device."""

    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_available = False
    _attr_hvac_modes = []
    _attr_preset_modes = []
    _attr_min_temp = 1
    _attr_max_temp = 30
    _hvac_mode = HVACMode.HEAT
    _current_temperature: float | None = None
    _new_target_temperature: float | None = None
    _target_temperature: float | None = None
    _away_mode_a: int | None = None
    _away_mode_b: int | None = None
    _away_state_a = False
    _away_state_b = False
    _current_operation: HVACAction | None = None
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, gw_dev, options):
        """Initialize the device."""
        self._gateway = gw_dev
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, gw_dev.gw_id, hass=gw_dev.hass
        )
        self.friendly_name = gw_dev.name
        self._attr_name = self.friendly_name
        self.floor_temp = options.get(CONF_FLOOR_TEMP, DEFAULT_FLOOR_TEMP)
        self.temp_read_precision = options.get(CONF_READ_PRECISION)
        self.temp_set_precision = options.get(CONF_SET_PRECISION)
        self.temporary_ovrd_mode = options.get(CONF_TEMPORARY_OVRD_MODE, True)
        self._unsub_options = None
        self._unsub_updates = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gw_dev.gw_id)},
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            name=gw_dev.name,
            sw_version=gw_dev.gw_version,
        )
        self._attr_unique_id = gw_dev.gw_id

    @callback
    def update_options(self, entry):
        """Update climate entity options."""
        self.floor_temp = entry.options[CONF_FLOOR_TEMP]
        self.temp_read_precision = entry.options[CONF_READ_PRECISION]
        self.temp_set_precision = entry.options[CONF_SET_PRECISION]
        self.temporary_ovrd_mode = entry.options[CONF_TEMPORARY_OVRD_MODE]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Connect to the OpenTherm Gateway device."""
        _LOGGER.debug("Added OpenTherm Gateway climate device %s", self.friendly_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )
        self._unsub_options = async_dispatcher_connect(
            self.hass, self._gateway.options_update_signal, self.update_options
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from updates from the component."""
        _LOGGER.debug("Removing OpenTherm Gateway climate %s", self.friendly_name)
        self._unsub_options()
        self._unsub_updates()

    @callback
    def receive_report(self, status):
        """Receive and handle a new report from the Gateway."""
        self._attr_available = status != gw_vars.DEFAULT_STATUS
        ch_active = status[gw_vars.BOILER].get(gw_vars.DATA_SLAVE_CH_ACTIVE)
        flame_on = status[gw_vars.BOILER].get(gw_vars.DATA_SLAVE_FLAME_ON)
        cooling_active = status[gw_vars.BOILER].get(gw_vars.DATA_SLAVE_COOLING_ACTIVE)
        if ch_active and flame_on:
            self._current_operation = HVACAction.HEATING
            self._hvac_mode = HVACMode.HEAT
        elif cooling_active:
            self._current_operation = HVACAction.COOLING
            self._hvac_mode = HVACMode.COOL
        else:
            self._current_operation = HVACAction.IDLE

        self._current_temperature = status[gw_vars.THERMOSTAT].get(
            gw_vars.DATA_ROOM_TEMP
        )
        temp_upd = status[gw_vars.THERMOSTAT].get(gw_vars.DATA_ROOM_SETPOINT)

        if self._target_temperature != temp_upd:
            self._new_target_temperature = None
        self._target_temperature = temp_upd

        # GPIO mode 5: 0 == Away
        # GPIO mode 6: 1 == Away
        gpio_a_state = status[gw_vars.OTGW].get(gw_vars.OTGW_GPIO_A)
        if gpio_a_state == 5:
            self._away_mode_a = 0
        elif gpio_a_state == 6:
            self._away_mode_a = 1
        else:
            self._away_mode_a = None
        gpio_b_state = status[gw_vars.OTGW].get(gw_vars.OTGW_GPIO_B)
        if gpio_b_state == 5:
            self._away_mode_b = 0
        elif gpio_b_state == 6:
            self._away_mode_b = 1
        else:
            self._away_mode_b = None
        if self._away_mode_a is not None:
            self._away_state_a = (
                status[gw_vars.OTGW].get(gw_vars.OTGW_GPIO_A_STATE) == self._away_mode_a
            )
        if self._away_mode_b is not None:
            self._away_state_b = (
                status[gw_vars.OTGW].get(gw_vars.OTGW_GPIO_B_STATE) == self._away_mode_b
            )
        self.async_write_ha_state()

    @property
    def precision(self):
        """Return the precision of the system."""
        if self.temp_read_precision:
            return self.temp_read_precision
        if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC operation."""
        return self._current_operation

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return self._hvac_mode

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        _LOGGER.warning("Changing HVAC mode is not supported")

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._current_temperature is None:
            return None
        if self.floor_temp is True:
            if self.precision == PRECISION_HALVES:
                return int(2 * self._current_temperature) / 2
            if self.precision == PRECISION_TENTHS:
                return int(10 * self._current_temperature) / 10
            return int(self._current_temperature)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._new_target_temperature or self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        if self.temp_set_precision:
            return self.temp_set_precision
        if self.hass.config.units.temperature_unit == UnitOfTemperature.CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def preset_mode(self):
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
