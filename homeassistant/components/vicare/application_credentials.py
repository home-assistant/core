"""application_credentials platform the Viessmann ViCare integration."""

import base64
import enum
import hashlib
import logging
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

_LOGGER = logging.getLogger(__name__)


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


class CodeChallengeMethod(enum.Enum):
    """Possible options for OAuth2 code challenge method."""

    plain = "plain"
    s265 = "S256"


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
        self.code_verifier, self.code_challenge = self._generateCodeChallengePair()
        self.code_challenge_method = CodeChallengeMethod.s265.value

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return self._name or self.client_id

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "code_challenge": self.code_challenge,  # PKCE
            "code_challenge_method": self.code_challenge_method,
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

    def _generateCodeChallengePair(self) -> tuple:
        # code_verifier = secrets.token_urlsafe(128).decode('utf-8')
        # code challenge must not be larger than 128 chars
        code_verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("utf-8")).digest()
        ).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")

        return (code_verifier, code_challenge)
