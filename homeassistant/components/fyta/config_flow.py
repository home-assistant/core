"""Config flow for FYTA integration."""

from __future__ import annotations

import logging
from typing import Any

from fyta_cli.fyta_connector import FytaConnector
from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class FytaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fyta."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        errors = {}
        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            fyta = FytaConnector(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

            try:
                await fyta.login()
            except FytaConnectionError:
                errors["base"] = "cannot_connect"
            except FytaAuthentificationError:
                errors["base"] = "invalid_auth"
            except FytaPasswordError:
                errors["base"] = "invalid_auth"
                errors[CONF_PASSWORD] = "password_error"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
            finally:
                await fyta.client.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
