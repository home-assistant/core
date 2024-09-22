"""Config flow for Weheat."""

from collections.abc import Mapping
import logging
from typing import Any

from weheat.abstractions.user import get_user_id_from_token

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import API_URL, DOMAIN, ENTRY_TITLE, OAUTH2_SCOPES


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Weheat OAuth2 authentication."""

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
        }

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Override the create entry method to change to the step to find the heat pumps."""
        # get the user id and use that as unique id for this entry
        user_id = await get_user_id_from_token(
            API_URL, data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        )
        if not self.reauth_entry:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=ENTRY_TITLE, data=data)

        if self.reauth_entry.unique_id == user_id:
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                unique_id=user_id,
                data={**self.reauth_entry.data, **data},
            )

        return self.async_abort(reason="wrong_account")

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
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
