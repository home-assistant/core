"""Config flow for Minut Point."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Minut Point OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

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
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        user_id = str(data[CONF_TOKEN]["user_id"])
        await self.async_set_unique_id(user_id)
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Minut Point",
                data={**data, CONF_WEBHOOK_ID: async_generate_id()},
            )

        reauth_entry = self._get_reauth_entry()
        if reauth_entry.unique_id is not None:
            self._abort_if_unique_id_mismatch(reason="wrong_account")

        _LOGGER.debug("user_id: %s", user_id)
        return self.async_update_reload_and_abort(
            reauth_entry, data_updates=data, unique_id=user_id
        )
