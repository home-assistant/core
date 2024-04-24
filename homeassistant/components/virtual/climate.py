"""Provide support for a virtual thermostat."""

import asyncio
import logging
import math
from typing import Any, cast

import numpy as np
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    DOMAIN as PLATFORM_DOMAIN,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.rasc.helpers import Dataset, load_dataset
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_entity_configs
from .const import (
    ATTR_GROUP_NAME,
    COMPONENT_DOMAIN,
    COMPONENT_NETWORK,
    CONF_COORDINATED,
    CONF_SIMULATE_NETWORK,
)
from .coordinator import VirtualDataUpdateCoordinator
from .entity import CoordinatedVirtualEntity, VirtualEntity, virtual_schema
from .network import NetworkProxy

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

CONF_INITIAL_TEMPERATURE = "initial_temperature"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"

DEFAULT_THERMOSTAT_VALUE = "on"
DEFAULT_INITIAL_TEMPERATURE = 68.0
DEFAULT_INITIAL_HVAC_MODE = HVACMode.HEAT

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(
        DEFAULT_THERMOSTAT_VALUE,
        {
            vol.Optional(
                CONF_INITIAL_TEMPERATURE, default=DEFAULT_INITIAL_TEMPERATURE
            ): cv.positive_float,
            vol.Optional(
                CONF_INITIAL_HVAC_MODE, default=DEFAULT_INITIAL_HVAC_MODE
            ): cv.string,
        },
    )
)
THERMOSTAT_SCHEMA = vol.Schema(
    virtual_schema(
        DEFAULT_THERMOSTAT_VALUE,
        {
            vol.Optional(
                CONF_INITIAL_TEMPERATURE, default=DEFAULT_INITIAL_TEMPERATURE
            ): cv.positive_float,
            vol.Optional(
                CONF_INITIAL_HVAC_MODE, default=DEFAULT_INITIAL_HVAC_MODE
            ): cv.string,
        },
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up thermostats."""

    coordinator: VirtualDataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        entry.entry_id
    ]
    entities: list[VirtualThermostat] = []
    for entity_config in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity_config = THERMOSTAT_SCHEMA(entity_config)
        if entity_config[CONF_COORDINATED]:
            entity = cast(
                VirtualThermostat,
                CoordinatedVirtualThermostat(entity_config, coordinator),
            )
        else:
            entity = VirtualThermostat(entity_config)

        if entity_config[CONF_SIMULATE_NETWORK]:
            entity = cast(VirtualThermostat, NetworkProxy(entity))
            hass.data[COMPONENT_NETWORK][entity.entity_id] = entity

        entities.append(entity)

    async_add_entities(entities)


class VirtualThermostat(VirtualEntity, ClimateEntity):
    """Representation of a Virtual thermostat."""

    def __init__(self, config):
        """Initialize the Virtual thermostat device."""
        super().__init__(config, PLATFORM_DOMAIN)

        self._dataset = load_dataset(Dataset.THERMOSTAT)

        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        self._attr_supported_features = (
            ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
        )
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_preset_modes = [PRESET_NONE]

        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_preset_mode = PRESET_NONE
        self._attr_min_temp = 62.0
        self._attr_max_temp = 85.0

        self._task: asyncio.Task | None = None

        _LOGGER.info("VirtualThermostat: %s created", self.name)

    def _create_state(self, config):
        super()._create_state(config)

        self._attr_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
        self._attr_current_temperature = config.get(CONF_INITIAL_TEMPERATURE)
        self._attr_target_temperature = config.get(CONF_INITIAL_TEMPERATURE)

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        self._attr_hvac_mode = state.attributes.get(
            ATTR_HVAC_MODE, config.get(CONF_INITIAL_HVAC_MODE)
        )
        self._attr_current_temperature = state.attributes.get(
            ATTR_CURRENT_TEMPERATURE, config.get(CONF_INITIAL_TEMPERATURE)
        )
        self._attr_target_temperature = state.attributes.get(
            ATTR_TEMPERATURE, config.get(CONF_INITIAL_TEMPERATURE)
        )

    def _update_attributes(self):
        super()._update_attributes()
        self._attr_extra_state_attributes.update(
            {
                name: value
                for name, value in (
                    (ATTR_CURRENT_TEMPERATURE, self._attr_current_temperature),
                    (ATTR_TEMPERATURE, self._attr_target_temperature),
                    (ATTR_HVAC_MODE, self._attr_hvac_mode),
                )
                if value is not None
            }
        )

    @property
    def is_on(self) -> bool:
        """Return true if thermostat is on."""
        return self.hvac_mode != HVACMode.OFF

    async def _async_update_temperature(self, target_temperature):
        if self._dataset is not None:
            start = math.floor(self._attr_current_temperature)
            target = math.floor(target_temperature)
            action = f"{start},{target}"
            if action in self._dataset:
                action_length = np.random.choice(self._dataset[action])
            else:
                start_keys = list(
                    filter(lambda key: key.startswith(str(start)), self._dataset.keys())
                )
                max_key = max(start_keys)
                max_action_length = np.random.choice(self._dataset[max_key])
                max_target = int(max_key.split(",")[-1])
                action_length = (
                    max_action_length / (max_target - start) * (target - start)
                )
        else:
            action_length = 1
        try:
            step = (target_temperature - self._attr_current_temperature) / action_length
            while True:
                self._attr_current_temperature += step
                if self._attr_current_temperature >= self.max_temp:
                    self._attr_current_temperature = self.max_temp
                    self._update_attributes()
                    break
                if self._attr_current_temperature <= self.min_temp:
                    self._attr_current_temperature = self.min_temp
                    self._update_attributes()
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            if self._attr_current_temperature >= self.max_temp:
                self._attr_current_temperature = self.max_temp
            elif self._attr_current_temperature <= self.min_temp:
                self._attr_current_temperature = self.min_temp
            self._update_attributes()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        self._attr_target_temperature = temperature
        self._update_attributes()
        self._task = self.hass.async_create_task(
            self._async_update_temperature(temperature)
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._update_attributes()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._attr_preset_mode = preset_mode
        self._update_attributes()


class CoordinatedVirtualThermostat(CoordinatedVirtualEntity, VirtualThermostat):
    """Representation of a Virtual thermostat."""

    def __init__(self, config, coordinator):
        """Initialize the Virtual thermostat device."""
        CoordinatedVirtualEntity.__init__(self, coordinator)
        VirtualThermostat.__init__(self, config)
