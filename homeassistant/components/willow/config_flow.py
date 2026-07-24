"""Config flow for Willow."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .client import WillowClient
from .const import DOMAIN, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET
from .exceptions import WillowAuthError


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Willow OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        scopes = ["read"]
        return {"scope": " ".join(scopes)}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Willow"),
        )
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""

        willow = WillowClient(
            session=aiohttp_client.async_get_clientsession(self.hass),
            token=data[CONF_TOKEN][CONF_ACCESS_TOKEN],
        )

        try:
            profile = await willow.get_profile()
        except WillowAuthError:
            return self.async_abort(reason="invalid_auth")
        except Exception:
            self.logger.exception("Unexpected error")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(str(profile["id"]))
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=profile["username"],
                data=data,
            )

        self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)

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
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
