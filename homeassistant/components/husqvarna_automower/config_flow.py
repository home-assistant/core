"""Config flow to add the integration via the UI."""

from collections.abc import Mapping
import logging
from typing import Any

from aioautomower.utils import structure_token

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

CONF_USER_ID = "user_id"
HUSQVARNA_DEV_PORTAL_URL = "https://developer.husqvarnagroup.cloud/applications"


class HusqvarnaConfigFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    VERSION = 1
    DOMAIN = DOMAIN
    reauth_entry: ConfigEntry | None = None

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow."""
        token = data[CONF_TOKEN]
        if "amc:api" not in token["scope"] and not self.reauth_entry:
            return self.async_abort(reason="missing_amc_scope")
        user_id = token[CONF_USER_ID]
        if self.reauth_entry:
            if "amc:api" not in token["scope"]:
                return self.async_update_reload_and_abort(
                    self.reauth_entry, data=data, reason="missing_amc_scope"
                )
            if self.reauth_entry.unique_id != user_id:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(self.reauth_entry, data=data)
        structured_token = structure_token(token[CONF_ACCESS_TOKEN])
        first_name = structured_token.user.first_name
        last_name = structured_token.user.last_name
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{NAME} of {first_name} {last_name}",
            data=data,
        )

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self.reauth_entry is not None:
            if "amc:api" not in self.reauth_entry.data["token"]["scope"]:
                return await self.async_step_missing_scope()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_missing_scope(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth for missing scope."""
        if user_input is None and self.reauth_entry is not None:
            token_structured = structure_token(
                self.reauth_entry.data["token"]["access_token"]
            )
            return self.async_show_form(
                step_id="missing_scope",
                description_placeholders={
                    "application_url": f"{HUSQVARNA_DEV_PORTAL_URL}/{token_structured.client_id}"
                },
            )
        return await self.async_step_user()
