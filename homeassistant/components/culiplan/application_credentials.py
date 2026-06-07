"""Application credentials platform for the Culiplan integration.

The Culiplan backend is a public OAuth 2.1 client: no client_secret, PKCE
(S256) mandatory. Home Assistant's default ``LocalOAuth2Implementation``
does not send ``code_challenge`` / ``code_verifier``, so we ship a thin
subclass that does.
"""

import base64
import hashlib
import secrets
from typing import Any

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import OAUTH2_AUTHORIZE, OAUTH2_SCOPES, OAUTH2_TOKEN


def _generate_pkce_pair() -> tuple[str, str]:
    """Return a ``(verifier, challenge)`` pair for PKCE S256."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class CuliplanOAuth2Implementation(AuthImplementation):
    """OAuth2 implementation with PKCE (S256) for the Culiplan public client."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialise the implementation and generate a fresh PKCE pair."""
        super().__init__(hass, auth_domain, credential, authorization_server)
        self._code_verifier, self._code_challenge = _generate_pkce_pair()

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Return the extra parameters appended to the /authorize URL."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            "code_challenge": self._code_challenge,
            "code_challenge_method": "S256",
        }

    async def _token_request(self, data: dict[str, Any]) -> dict[Any, Any]:
        """Inject ``code_verifier`` on the authorisation-code exchange."""
        if data.get("grant_type") == "authorization_code":
            data["code_verifier"] = self._code_verifier
        return await super()._token_request(data)


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return a PKCE-enabled auth implementation."""
    return CuliplanOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        ),
    )


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return the Culiplan OAuth authorisation server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
