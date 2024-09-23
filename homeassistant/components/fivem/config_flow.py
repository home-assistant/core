"""Config flow for FiveM integration."""

from __future__ import annotations

import logging
from typing import Any

from fivem import FiveM, FiveMServerOfflineError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 30120

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""

    fivem = FiveM(data[CONF_HOST], data[CONF_PORT])
    info = await fivem.get_info_raw()

    game_name = info.get("vars")["gamename"]
    if game_name is None or game_name != "gta5":
        raise InvalidGameNameError


class FiveMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FiveM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(user_input)
        except FiveMServerOfflineError:
            errors["base"] = "cannot_connect"
        except InvalidGameNameError:
            errors["base"] = "invalid_game_name"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._async_abort_entries_match(user_input)
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidGameNameError(Exception):
    """Handle errors in the game name from the api."""
