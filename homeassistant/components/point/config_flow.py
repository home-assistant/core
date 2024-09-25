"""Config flow for Minut Point."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Minut Point OAuth2 authentication."""

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_import(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML."""
        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        user_id = str(data[CONF_TOKEN]["user_id"])
        if not self.reauth_entry:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Minut Point",
                data={**data, CONF_WEBHOOK_ID: async_generate_id()},
            )

        if (
            self.reauth_entry.unique_id is None
            or self.reauth_entry.unique_id == user_id
        ):
            logging.debug("user_id: %s", user_id)
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                data={**self.reauth_entry.data, **data},
                unique_id=user_id,
            )

        return self.async_abort(reason="wrong_account")
