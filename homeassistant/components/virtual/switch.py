"""Provide support for a virtual switch."""

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as PLATFORM_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_entity_configs
from .const import (
    ATTR_GROUP_NAME,
    COMPONENT_DOMAIN,
    COMPONENT_NETWORK,
    CONF_CLASS,
    CONF_COORDINATED,
    CONF_INITIAL_VALUE,
    CONF_SIMULATE_NETWORK,
)
from .coordinator import VirtualDataUpdateCoordinator
from .entity import CoordinatedVirtualEntity, VirtualEntity, virtual_schema
from .network import NetworkProxy

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

DEFAULT_SWITCH_VALUE = "off"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(
        DEFAULT_SWITCH_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
        },
    )
)
SWITCH_SCHEMA = vol.Schema(
    virtual_schema(
        DEFAULT_SWITCH_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
        },
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    coordinator: VirtualDataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        entry.entry_id
    ]
    entities: list[VirtualSwitch] = []
    for entity_config in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity_config = SWITCH_SCHEMA(entity_config)
        if entity_config[CONF_COORDINATED]:
            entity = cast(
                VirtualSwitch, CoordinatedVirtualSwitch(entity_config, coordinator)
            )
        else:
            entity = VirtualSwitch(entity_config)

        if entity_config[CONF_SIMULATE_NETWORK]:
            entity = cast(VirtualSwitch, NetworkProxy(entity))
            hass.data[COMPONENT_NETWORK][entity.entity_id] = entity

        entities.append(entity)

    async_add_entities(entities)


class VirtualSwitch(VirtualEntity, SwitchEntity):
    """Representation of a Virtual switch."""

    def __init__(self, config):
        """Initialize the Virtual switch device."""
        super().__init__(config, PLATFORM_DOMAIN)

        self._attr_device_class = config.get(CONF_CLASS)

        _LOGGER.info("VirtualSwitch: %s created", self.name)

    def _create_state(self, config):
        super()._create_state(config)

        self._attr_is_on = config.get(CONF_INITIAL_VALUE).lower() == STATE_ON

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        self._attr_is_on = state.state.lower() == STATE_ON

    def _update_attributes(self):
        super()._update_attributes()
        self._attr_extra_state_attributes.update(
            {
                name: value
                for name, value in ((ATTR_DEVICE_CLASS, self._attr_device_class),)
                if value is not None
            }
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        self._attr_is_on = False


class CoordinatedVirtualSwitch(CoordinatedVirtualEntity, VirtualSwitch):
    """Representation of a Virtual switch."""

    def __init__(self, config, coordinator):
        """Initialize the Virtual switch device."""
        CoordinatedVirtualEntity.__init__(self, coordinator)
        VirtualSwitch.__init__(self, config)
