"""Provide support for a virtual fan.

Borrowed heavily from components/demo/fan.py
"""

from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as PLATFORM_DOMAIN,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
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

CONF_DIRECTION = "direction"
CONF_MODES = "modes"
CONF_OSCILLATE = "oscillate"
CONF_PERCENTAGE = "percentage"
CONF_SPEED = "speed"
CONF_SPEED_COUNT = "speed_count"

DEFAULT_FAN_VALUE = "off"

BASE_SCHEMA = virtual_schema(
    DEFAULT_FAN_VALUE,
    {
        vol.Optional(CONF_SPEED, default=False): cv.boolean,
        vol.Optional(CONF_SPEED_COUNT, default=0): cv.positive_int,
        vol.Optional(CONF_OSCILLATE, default=False): cv.boolean,
        vol.Optional(CONF_DIRECTION, default=False): cv.boolean,
        vol.Optional(CONF_MODES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    },
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BASE_SCHEMA)

FAN_SCHEMA = vol.Schema(BASE_SCHEMA)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fans."""

    coordinator: VirtualDataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        entry.entry_id
    ]
    entities: list[VirtualFan] = []
    for entity_config in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity_config = FAN_SCHEMA(entity_config)
        if entity_config[CONF_COORDINATED]:
            entity = cast(VirtualFan, CoordinatedVirtualFan(entity_config, coordinator))
        else:
            entity = VirtualFan(entity_config)

        if entity_config[CONF_SIMULATE_NETWORK]:
            entity = cast(VirtualFan, NetworkProxy(entity))
            hass.data[COMPONENT_NETWORK][entity.entity_id] = entity

        entities.append(entity)

    async_add_entities(entities)


class VirtualFan(VirtualEntity, FanEntity):
    """A demonstration fan component."""

    def __init__(self, config):
        """Initialize the entity."""
        super().__init__(config, PLATFORM_DOMAIN)

        # Modes if supported
        self._attr_preset_modes = config.get(CONF_MODES)

        # Try for speed count then speed.
        #  - speed_count; number of speeds we support
        #  - speed == True; 3 speeds
        #  - speed == False; no speeds
        self._attr_speed_count = config.get(CONF_SPEED_COUNT)
        if config.get(CONF_SPEED, False):
            self._attr_speed_count = 3

        self._attr_supported_features = 0
        if self._attr_speed_count > 0:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
        if config.get(CONF_OSCILLATE, False):
            self._attr_supported_features |= FanEntityFeature.OSCILLATE
        if config.get(CONF_DIRECTION, False):
            self._attr_supported_features |= FanEntityFeature.DIRECTION

        _LOGGER.info("VirtualFan: %s created", self.name)

    def _create_state(self, config):
        super()._create_state(config)

        if self._attr_supported_features & FanEntityFeature.DIRECTION:
            self._attr_current_direction = "forward"
        if self._attr_supported_features & FanEntityFeature.OSCILLATE:
            self._attr_oscillating = False
        self._attr_percentage = None
        self._attr_preset_mode = None

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        if self._attr_supported_features & FanEntityFeature.DIRECTION:
            self._attr_current_direction = state.attributes.get(ATTR_DIRECTION)
        if self._attr_supported_features & FanEntityFeature.OSCILLATE:
            self._attr_oscillating = state.attributes.get(ATTR_OSCILLATING)
        self._attr_percentage = state.attributes.get(ATTR_PERCENTAGE)
        self._attr_preset_mode = state.attributes.get(ATTR_PRESET_MODE)

    def _update_attributes(self):
        super()._update_attributes()
        self._attr_extra_state_attributes.update(
            {
                name: value
                for name, value in (
                    (ATTR_DIRECTION, self._attr_current_direction),
                    (ATTR_OSCILLATING, self._attr_oscillating),
                    (ATTR_PERCENTAGE, self._attr_percentage),
                    (ATTR_PRESET_MODE, self._attr_preset_mode),
                )
                if value is not None
            }
        )

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        self._attr_percentage = percentage
        self._attr_preset_mode = None
        self._update_attributes()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.preset_modes is None:
            raise ValueError("The device does no support preset mode")
        if preset_mode in self.preset_modes:
            self._attr_preset_mode = preset_mode
            self._attr_percentage = None
            self._update_attributes()
        else:
            raise ValueError(f"Invalid preset mode: {preset_mode}")

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity."""
        if preset_mode:
            self.set_preset_mode(preset_mode)
            return

        if percentage is None:
            percentage = 67
        self.set_percentage(percentage)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the entity."""
        self.set_percentage(0)

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self._attr_current_direction = direction
        self._update_attributes()

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        self._attr_oscillating = oscillating
        self._update_attributes()


class CoordinatedVirtualFan(CoordinatedVirtualEntity, VirtualFan):
    """Representation of a Virtual switch."""

    def __init__(self, config, coordinator):
        """Initialize the Virtual switch device."""
        CoordinatedVirtualEntity.__init__(self, coordinator)
        VirtualFan.__init__(self, config)
