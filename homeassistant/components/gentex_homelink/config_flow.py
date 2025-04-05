"""Config flow for homelink."""

import asyncio
import logging
from typing import Any

import botocore.exceptions
from homelink.auth.srp_auth import SRPAuth
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN
from .oauth2 import SRPAuthImplementation

_LOGGER = logging.getLogger(__name__)


class SRPFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle homelink OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        """Set up the flow handler."""
        super().__init__()
        self.flow_impl = SRPAuthImplementation(self.hass, DOMAIN)

    @property
    def logger(self):
        """Get the logger."""
        return _LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for username and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info(user_input)
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})

            srp_auth = SRPAuth()
            loop = asyncio.get_running_loop()
            try:
                tokens = await loop.run_in_executor(
                    None,
                    srp_auth.async_get_access_token,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except botocore.exceptions.ClientError:
                errors["base"] = "Error authenticating HomeLink account"
            except Exception:
                _LOGGER.exception("An unexpected error occurred")

                errors["base"] = "unknown"
            else:
                _LOGGER.info("Got tokens, passing to creation")
                self.external_data = {"tokens": tokens}
                return await self.async_step_creation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )
