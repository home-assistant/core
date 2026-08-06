"""Config flow for the A Better Routeplanner integration."""

import logging
from typing import Any, override

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    StaticAuth,
    parse_unverified_identity,
)

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ABRP_APP_KEY, DOMAIN, OAUTH2_SCOPES
from .oauth import AbetterrouteplannerOAuth2Implementation


class AbetterrouteplannerFlowHandler(
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
        """Extra data appended to the authorize URL.

        Scopes belong on the flow, not the implementation, so they still apply
        when cloud account linking supplies the implementation.
        """
        return {**super().extra_authorize_data, "scope": " ".join(OAUTH2_SCOPES)}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # The built-in implementation has no Application Credentials entry, so
        # the first flow must register it before any config entry exists.
        if not await config_entry_oauth2_flow.async_get_implementations(
            self.hass, DOMAIN
        ):
            config_entry_oauth2_flow.async_register_implementation(
                self.hass, DOMAIN, AbetterrouteplannerOAuth2Implementation(self.hass)
            )
        return await super().async_step_user(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a successful OAuth2 authorization."""
        # The ``oidc`` scope guarantees an id_token; without one we cannot bind
        # the entry to a verified account.
        id_token = data["token"].get("id_token")
        if id_token is None:
            return self.async_abort(reason="oauth_error")
        # A bad id_token — distinct from the API-auth use of the same exception
        # in ``async_get_vehicles`` below.
        try:
            identity = parse_unverified_identity(id_token)
        except AbrpAuthError:
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(identity.subject)

        self._abort_if_unique_id_configured()

        title = (
            f"{self.flow_impl.name} ({identity.display_name})"
            if identity.display_name
            else self.flow_impl.name
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

        # The garage is only re-read at setup, so an entry created against an
        # empty garage would load green and stay empty until a manual reload.
        if not vehicles:
            return self.async_abort(reason="no_vehicles")

        return self.async_create_entry(title=title, data=data)
