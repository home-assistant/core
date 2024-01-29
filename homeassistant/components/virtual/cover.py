"""This component provides support for a virtual cover."""

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.cover import (
    DOMAIN as PLATFORM_DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_CLOSED
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.typing import HomeAssistantType

from . import get_entity_configs
from .const import *
from .entity import VirtualEntity, virtual_schema

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [COMPONENT_DOMAIN]

DEFAULT_COVER_VALUE = "open"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    virtual_schema(
        DEFAULT_COVER_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
        },
    )
)
COVER_SCHEMA = vol.Schema(
    virtual_schema(
        DEFAULT_COVER_VALUE,
        {
            vol.Optional(CONF_CLASS): cv.string,
        },
    )
)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> None:
    _LOGGER.debug("setting up the entries...")

    entities = []
    for entity in get_entity_configs(
        hass, entry.data[ATTR_GROUP_NAME], PLATFORM_DOMAIN
    ):
        entity = COVER_SCHEMA(entity)
        entities.append(VirtualCover(entity))
    async_add_entities(entities)


class VirtualCover(VirtualEntity, CoverEntity):
    """Representation of a Virtual cover."""

    def __init__(self, config):
        """Initialize the Virtual cover device."""
        super().__init__(config, PLATFORM_DOMAIN)

        self._attr_device_class = config.get(CONF_CLASS)
        self._attr_supported_features = CoverEntityFeature(
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        _LOGGER.info(f"VirtualCover: {self.name} created")

    def _create_state(self, config):
        super()._create_state(config)

        self._attr_is_closed = config.get(CONF_INITIAL_VALUE).lower() == STATE_CLOSED

    def _restore_state(self, state, config):
        super()._restore_state(state, config)

        self._attr_is_closed = state.state.lower() == STATE_CLOSED

    def _update_attributes(self):
        super()._update_attributes()
        self._attr_extra_state_attributes.update(
            {
                name: value
                for name, value in ((ATTR_DEVICE_CLASS, self._attr_device_class),)
                if value is not None
            }
        )

    def open_cover(self, **kwargs: Any) -> None:
        _LOGGER.info(f"opening {self.name}")
        self._attr_is_closed = False

    def close_cover(self, **kwargs: Any) -> None:
        _LOGGER.info(f"closing {self.name}")
        self._attr_is_closed = True
