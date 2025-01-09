"""Config flow for Electric Kiwi."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from electrickiwi_api import ElectricKiwiApi

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import DOMAIN, SCOPE_VALUES


class ElectricKiwiOauth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Electric Kiwi OAuth2 authentication."""

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
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for Electric Kiwi."""

        ek_api = ElectricKiwiApi(
            api.ConfigFlowElectricKiwiAuth(self.hass, data["token"]["access_token"])
        )

        session = await ek_api.get_active_session()

        if len(session.customer_numbers) == 0:
            return self.async_abort(reason="no_customers")

        unique_id = "_".join(str(num) for num in session.customer_numbers)
        existing_entry = await self.async_set_unique_id(unique_id)

        if existing_entry:
            return self.async_update_reload_and_abort(existing_entry, data=data)
        return self.async_create_entry(title=unique_id, data=data)
