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
    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register the built-in implementation, then pick one.

        Starting a flow imports the config flow platform without running
        ``async_setup``, so on a fresh install nothing is registered yet and the
        flow has to register the built-in implementation itself. It builds a new
        instance every time because the PKCE verifier is generated in the
        constructor and RFC 7636 wants one per authorization request.
        """
        config_entry_oauth2_flow.async_register_implementation(
            self.hass, DOMAIN, AbetterrouteplannerOAuth2Implementation(self.hass)
        )
        return await super().async_step_pick_implementation(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a successful OAuth2 authorization.

        The entry is bound to the id_token's subject, so a missing or malformed
        id_token — one the ``oidc`` scope guarantees — aborts rather than
        binding the entry to an unverified account. An empty garage aborts too:
        the garage is only re-read at setup, so such an entry would load green
        and stay empty until a manual reload.
        """
        id_token = data["token"].get("id_token")
        if id_token is None:
            return self.async_abort(reason="oauth_error")
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

        if not vehicles:
            return self.async_abort(reason="no_vehicles")

        return self.async_create_entry(title=title, data=data)
