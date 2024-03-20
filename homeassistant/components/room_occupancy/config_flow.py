"""Config flow for Room Occupancy integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ACTIVE_STATES,
    CONF_ENTITIES_KEEP,
    CONF_ENTITIES_TOGGLE,
    CONF_TIMEOUT,
    DEFAULT_ACTIVE_STATES,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RoomOccupancyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Room Occupancy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        all_entities = []
        for domain in (
            "sensor",
            "binary_sensor",
            "timer",
            "input_boolean",
            "media_player",
        ):
            all_entities += self.hass.states.async_entity_ids(domain)
        _LOGGER.debug("all entities: %s", all_entities)
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
                    vol.Required(
                        CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                    ): cv.positive_int,
                    vol.Required(CONF_ENTITIES_TOGGLE, default=[]): cv.multi_select(
                        sorted(all_entities)
                    ),
                    vol.Required(CONF_ENTITIES_KEEP, default=[]): cv.multi_select(
                        sorted(all_entities)
                    ),
                    vol.Optional(
                        CONF_ACTIVE_STATES, default=DEFAULT_ACTIVE_STATES
                    ): cv.string,
                }
            ),
            errors=errors,
        )
