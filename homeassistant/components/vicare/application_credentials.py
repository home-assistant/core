"""Application credentials platform for Viessmann ViCare."""

from __future__ import annotations

import base64
import hashlib
import os
import re
from typing import Any

from PyViCare.PyViCareOAuthManager import AUTHORIZE_URL, TOKEN_URL

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

VICARE_SCOPES = [
    "IoT User",
    "offline_access",
]


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation with PKCE support."""
    return ViCareOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=AUTHORIZE_URL,
            token_url=TOKEN_URL,
        ),
    )


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code verifier and challenge pair."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8")
    code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    ).decode("utf-8")
    code_challenge = code_challenge.replace("=", "")

    return code_verifier, code_challenge


class ViCareOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """ViCare OAuth2 implementation with PKCE.

    Viessmann requires PKCE (Proof Key for Code Exchange) and does not use
    a client secret.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialize ViCare OAuth2 implementation."""
        super().__init__(
            hass,
            domain,
            credential.client_id,
            "",  # Viessmann does not use a client secret with PKCE
            authorization_server.authorize_url,
            authorization_server.token_url,
        )
        self._name = credential.name
        self._code_verifier, self._code_challenge = _generate_pkce_pair()

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return self._name or self.client_id

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "code_challenge": self._code_challenge,
            "code_challenge_method": "S256",
            "scope": " ".join(VICARE_SCOPES),
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": self._code_verifier,
            }
        )
