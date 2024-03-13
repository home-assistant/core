"""Config flow file for room occupancy."""
import logging

import voluptuous as vol

from homeassistant import config_entries
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


class RoomOccupancyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    async def async_step_user(self, user_input=None):
        """Setup new config item."""  # noqa: D401
        _LOGGER.debug(
            "config_flow.py async_step_user triggered, user_input: %s", user_input
        )
        if user_input is not None:
            _LOGGER.debug("user_input is not none!")
            _LOGGER.debug(user_input)
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        _LOGGER.debug("returning async_show_form!")
        return await self._show_setup_form(None, "user")

    async def _show_setup_form(self, errors=None, step_id="user"):
        """Show the setup form to the user."""
        # get a list of entities for interesting domains
        all_entities = []
        for domain in (
            "sensor",
            "binary_sensor",
            "timer",
            "input_boolean",
            "media_player",
        ):
            all_entities = all_entities + [
                list(self.hass.states.async_entity_ids(domain))
            ]
            # all_entities = all_entities + [
            #    entity for entity in self.hass.states.async_entity_ids(domain)
            # ]
        return self.async_show_form(
            step_id=step_id,
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
        )
