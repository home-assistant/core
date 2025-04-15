"""Config flow for Electric Kiwi."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from electrickiwi_api import ElectricKiwiApi
from electrickiwi_api.exceptions import ApiException

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import DOMAIN, SCOPE_VALUES


class ElectricKiwiOauth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Electric Kiwi OAuth2 authentication."""

    VERSION = 1
    MINOR_VERSION = 2
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPE_VALUES}

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
                description_placeholders={CONF_NAME: self._get_reauth_entry().title},
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for Electric Kiwi."""
        ek_api = ElectricKiwiApi(
            api.ConfigFlowElectricKiwiAuth(self.hass, data["token"]["access_token"])
        )

        try:
            session = await ek_api.get_active_session()
        except ApiException:
            return self.async_abort(reason="connection_error")

        unique_id = str(session.data.customer_number)
        await self.async_set_unique_id(unique_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=unique_id, data=data)
