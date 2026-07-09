"""Config flow for place."""

from collections.abc import Mapping
import logging
from typing import Any, override

import botocore.exceptions
import jwt
from place.auth import login
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN
from .oauth2 import SRPAuthImplementation

_LOGGER = logging.getLogger(__name__)


class SRPFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle place OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self):
        """Get the logger."""
        return _LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for username and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                tokens = await self.hass.async_add_executor_job(
                    login,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except botocore.exceptions.ClientError as err:
                _LOGGER.error("Failed to get tokens: %s", err)
                errors["base"] = "srp_auth_failed"
            except Exception:
                _LOGGER.exception("An unexpected error occurred")
                errors["base"] = "unknown"
            else:
                access_token = jwt.decode(
                    tokens["AuthenticationResult"]["AccessToken"],
                    options={"verify_signature": False},
                )
                sub = access_token["sub"]
                await self.async_set_unique_id(sub)
                self.flow_impl = SRPAuthImplementation(self.hass, DOMAIN)
                self.external_data = {
                    "tokens": tokens,
                    CONF_UNIQUE_ID: sub,
                    CONF_EMAIL: user_input[CONF_EMAIL].strip().lower(),
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
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
                ),
            )
        return await self.async_step_user(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        await self.async_set_unique_id(self.external_data[CONF_UNIQUE_ID])
        entry_title = self.context.get("title_placeholders", {"name": "Place"})["name"]
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data, title=entry_title
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(data=data, title=entry_title)
