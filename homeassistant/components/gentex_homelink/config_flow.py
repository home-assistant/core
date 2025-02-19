"""Config flow for homelink."""

import asyncio
import logging
import time
from typing import Any

import botocore.exceptions
from homelink.auth.srp_auth import SRPAuth
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class SRPFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow to handle homelink OAuth2 authentication."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for username and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
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
                new_token = {}
                new_token["access_token"] = tokens["AuthenticationResult"][
                    "AccessToken"
                ]
                new_token["refresh_token"] = tokens["AuthenticationResult"][
                    "RefreshToken"
                ]
                new_token["token_type"] = tokens["AuthenticationResult"]["TokenType"]
                new_token["expires_in"] = tokens["AuthenticationResult"]["ExpiresIn"]
                new_token["expires_at"] = (
                    time.time() + tokens["AuthenticationResult"]["ExpiresIn"]
                )

                return self.async_create_entry(
                    title=f"{user_input[CONF_EMAIL]} HomeLink integration",
                    data={
                        "token": new_token,
                        "auth_implementation": DOMAIN,
                        "last_update_id": None,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )
