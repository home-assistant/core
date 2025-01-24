"""Config flow for homelink."""

import asyncio
import time
from typing import Any

from homelink.auth.srp_auth import SRPAuth
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class SRPFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow to handle homelink OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for username and password."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({"email": user_input["email"]})

            srp_auth = SRPAuth()
            loop = asyncio.get_running_loop()
            try:
                tokens = await loop.run_in_executor(
                    None,
                    srp_auth.async_get_access_token,
                    user_input["email"],
                    user_input["password"],
                )
            except Exception:  # noqa: BLE001
                errors["base"] = "Error authenticating HomeLink account"
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
                    title="Token entry",
                    data={
                        "token": new_token,
                        "auth_implementation": DOMAIN,
                        "last_update_id": None,
                        "email": user_input["email"],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("email"): str, vol.Required("password"): str}
            ),
            errors=errors,
        )
