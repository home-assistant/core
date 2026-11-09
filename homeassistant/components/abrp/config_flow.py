"""Config flow for the A Better Routeplanner integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    StaticAuth,
    parse_unverified_identity,
)

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ABRP_APP_KEY, DOMAIN, OAUTH2_SCOPES


class AbrpFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle A Better Routeplanner OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH2_SCOPES)}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check we have the cloud integration set up."""
        if "cloud" not in self.hass.config.components:
            return self.async_abort(
                reason="cloud_not_enabled",
                description_placeholders={"default_config": "default_config"},
            )
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a successful OAuth2 authorization.

        The entry is bound to the id_token's subject, so a missing or malformed
        id_token — one the ``openid`` scope guarantees — aborts rather than
        binding the entry to an unverified account. A token without a
        refresh_token aborts as well: the entry could not outlive the access
        token, and the stream would retry it forever. On a new entry an empty
        garage aborts too: the garage is only re-read at setup, so such an entry
        would load green and stay empty until a manual reload.
        """
        try:
            identity = parse_unverified_identity(data["token"].get("id_token"))
        except AbrpAuthError:
            return self.async_abort(reason="oauth_error")
        if not data["token"].get("refresh_token"):
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(identity.subject)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )

        self._abort_if_unique_id_configured()

        title = (
            f"A Better Routeplanner ({identity.display_name})"
            if identity.display_name
            else "A Better Routeplanner"
        )

        client = AbrpClient(
            async_get_clientsession(self.hass),
            ABRP_APP_KEY,
            StaticAuth(data["token"]["access_token"]),
        )
        try:
            vehicles = await client.async_get_vehicles()
        except AbrpAuthError:
            return self.async_abort(reason="api_unauthorized")
        except AbrpApiError:
            return self.async_abort(reason="cannot_connect")

        if not vehicles:
            return self.async_abort(reason="no_vehicles")

        return self.async_create_entry(title=title, data=data)
