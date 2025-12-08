"""Config flow for homelink."""

from collections.abc import Mapping
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
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})

            srp_auth = SRPAuth()
            try:
                tokens = await self.hass.async_add_executor_job(
                    srp_auth.async_get_access_token,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except botocore.exceptions.ClientError:
                _LOGGER.exception("Error authenticating homelink account")
                errors["base"] = "srp_auth_failed"
            except Exception:
                _LOGGER.exception("An unexpected error occurred")
                errors["base"] = "unknown"
            else:
                self.external_data = {
                    "tokens": tokens,
                    CONF_EMAIL: user_input[CONF_EMAIL].lower(),
                }
                return await self.async_step_creation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
                ),
            )
        return await self.async_step_user(user_input)

    async def async_oauth_create_entry(
        self, data: dict
    ) -> config_entries.ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        await self.async_set_unique_id(data["token"][CONF_EMAIL])
        if self.source == config_entries.SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data,
            )
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
