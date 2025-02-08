"""Config flow for Withings."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiowithings import AuthScope

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_TITLE, DOMAIN


class WithingsFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": f"{AuthScope.USER_INFO},{AuthScope.USER_METRICS},"
            f"{AuthScope.USER_ACTIVITY},{AuthScope.USER_SLEEP_EVENTS}"
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={CONF_NAME: self._get_reauth_entry().title},
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        user_id = str(data[CONF_TOKEN]["userid"])
        await self.async_set_unique_id(user_id)
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=DEFAULT_TITLE,
                data={**data, CONF_WEBHOOK_ID: async_generate_id()},
            )

        self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(), data_updates=data
        )
