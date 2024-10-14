"""application_credentials platform the Viessmann ViCare integration."""

import base64
import hashlib
import os
import re
from typing import Any

# import secrets
from PyViCare.PyViCareOAuthManager import AUTHORIZE_URL, TOKEN_URL

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

SCOPES = ["IoT User"]


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation."""
    return OAuth2WithPKCEImplementation(
        hass,
        DOMAIN,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=AUTHORIZE_URL,
            token_url=TOKEN_URL,
        ),
    )


def _generateCodeChallengePair() -> tuple:
    # code_verifier = secrets.token_urlsafe(128).decode('utf-8')
    code_verifier = base64.urlsafe_b64encode(os.urandom(128)).decode("utf-8")
    code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("utf-8")).digest()
    ).decode("utf-8")
    code_challenge = code_challenge.replace("=", "")

    return (code_verifier, code_challenge)


class OAuth2WithPKCEImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Application Credentials local oauth2 with PKCE implementation."""

    code_verifier: str
    code_challenge: str

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialize AuthImplementation."""
        super().__init__(
            hass,
            auth_domain,
            credential.client_id,
            "",  # TODO: fix in LocalOAuth2Implementation
            # credential.client_secret,
            authorization_server.authorize_url,
            authorization_server.token_url,
        )
        self._name = credential.name
        # Init PKCE
        self.code_verifier, self.code_challenge = _generateCodeChallengePair()

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SCOPES),
            "code_challenge_method": "S256",
            "code_challenge": self.code_challenge,  # PKCE
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": self.code_verifier,  # PKCE
            }
        )
