"""Config flow for homelink."""

import logging
from typing import Any

import botocore.exceptions
from homelink.auth.srp_auth import SRPAuth
import jwt
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
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
    ) -> ConfigFlowResult:
        """Ask for username and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            srp_auth = SRPAuth()
            try:
                tokens = await self.hass.async_add_executor_job(
                    srp_auth.async_get_access_token,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except botocore.exceptions.ClientError:
                errors["base"] = "srp_auth_failed"
            except Exception:
                _LOGGER.exception("An unexpected error occurred")
                errors["base"] = "unknown"
            else:
                access_token = jwt.decode(
                    tokens["AuthenticationResult"]["AccessToken"],
                    options={"verify_signature": False},
                )
                await self.async_set_unique_id(access_token["sub"])
                self._abort_if_unique_id_configured()
                self.external_data = {"tokens": tokens}
                return await self.async_step_creation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )
