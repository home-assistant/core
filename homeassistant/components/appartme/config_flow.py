"""Config flow platform for Appartme Integration."""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import application_credentials
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow

from .application_credentials import async_get_authorization_server
from .const import DOMAIN, UPDATE_INTERVAL_DEFAULT, UPDATE_INTERVAL_MIN

_LOGGER = logging.getLogger(__name__)


class AppartmeConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Appartme System."""

    DOMAIN = DOMAIN

    @property
    def logger(self):
        """Return logger."""
        return _LOGGER

    async def async_oauth_create_entry(self, data):
        """Create an entry after OAuth authentication."""
        return self.async_create_entry(title="Appartme System", data=data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Define the options flow for reconfiguration."""
        return AppartmeOptionsFlow(config_entry)

    async def async_oauth_create_implementation(self):
        """Get OAuth2 implementation."""
        auth_server = await async_get_authorization_server(self.hass)
        client_credential = await application_credentials.async_get_client_credential(
            self.hass, DOMAIN
        )

        return config_entry_oauth2_flow.LocalOAuth2Implementation(
            self.hass,
            DOMAIN,
            client_id=client_credential.client_id,
            client_secret=client_credential.client_secret,
            authorize_url=auth_server.authorize_url,
            token_url=auth_server.token_url,
        )


class AppartmeOptionsFlow(OptionsFlow):
    """Handle options flow for Appartme System."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow.

        Args:
            config_entry: The configuration entry for the integration.

        """
        self.config_entry = config_entry

    async def async_step_init(self, user_input) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            update_interval_input = user_input.get("update_interval")
            try:
                update_interval = int(update_interval_input)
                if update_interval < UPDATE_INTERVAL_MIN:
                    errors["update_interval"] = "interval_too_short"
            except ValueError:
                errors["update_interval"] = "invalid_int"

            if not errors:
                # Save the options
                user_input["update_interval"] = (
                    update_interval  # Ensure it's stored as int
                )
                return self.async_create_entry(title="", data=user_input)

        # Get the current value or default to UPDATE_INTERVAL_DEFAULT
        current_interval = self.config_entry.options.get(
            "update_interval", UPDATE_INTERVAL_DEFAULT
        )

        # Define the options schema
        options_schema = vol.Schema(
            {vol.Required("update_interval", default=str(current_interval)): str}
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={"min_interval": str(UPDATE_INTERVAL_MIN)},
        )
