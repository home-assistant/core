"""Config flow for the Nintendo Switch Parental Controls integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pynintendoparental import Authenticator
from pynintendoparental.exceptions import HttpException, InvalidSessionTokenException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN

from .const import CONF_SESSION_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NintendoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nintendo Switch Parental Controls."""

    def __init__(self) -> None:
        """Initialize a new config flow instance."""
        self.auth = Authenticator.generate_login()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await self.auth.complete_login(
                    self.auth, user_input[CONF_API_TOKEN], False
                )
            except (ValueError, InvalidSessionTokenException, HttpException):
                errors["base"] = "invalid_auth"
            except Exception as exc:
                _LOGGER.exception("Unknown error during setup", exc_info=exc)
                errors["base"] = "unknown"
            else:
                if TYPE_CHECKING:
                    assert self.auth.account_id
                await self.async_set_unique_id(self.auth.account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self.auth.account_id,
                    data={
                        CONF_SESSION_TOKEN: self.auth.get_session_token,
                    },
                )
        return self.async_show_form(
            step_id="user",
            description_placeholders={"link": self.auth.login_url},
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )
