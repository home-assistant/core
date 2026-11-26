"""Config flow for Roth Touchline integration."""

import logging
from typing import Any, override

import probatio
from pytouchline_extended import TouchlineController, TouchlineError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): cv.string,
    }
)


async def _async_validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect, and return the controller ID."""
    host = data[CONF_HOST]

    try:
        state = await TouchlineController(url=host).fetch_async()
    except TouchlineError as err:
        _LOGGER.debug(
            "Error while connecting to Touchline controller at %s", host, exc_info=True
        )
        raise CannotConnect from err

    # The ID that the thermostats report as their owner identifies the controller.
    if not state.rooms or (controller_id := state.rooms[0].controller_id) is None:
        raise CannotConnect
    return str(controller_id)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class TouchlineConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                unique_id = await _async_validate_input(user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
