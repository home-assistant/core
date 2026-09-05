"""Provide oauth implementations for the Tesla Fleet integration."""

from typing import Any, override

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant

from .const import (
    AUTHORIZATION_PROFILE_SCOPES,
    AUTHORIZE_URL,
    SCOPES,
    TOKEN_URL,
    AuthorizationProfile,
)


def has_exact_energy_site_read_only_scopes(scopes: Any) -> bool:
    """Return whether the effective token has exactly the read-only scopes."""
    return (
        isinstance(scopes, list)
        and all(isinstance(scope, str) for scope in scopes)
        and len(scopes) == len(set(scopes))
        and set(scopes)
        == {
            str(scope)
            for scope in AUTHORIZATION_PROFILE_SCOPES[
                AuthorizationProfile.ENERGY_SITE_READ_ONLY
            ]
        }
    )


class TeslaUserImplementation(AuthImplementation):
    """Tesla Fleet API user Oauth2 implementation."""

    def __init__(
        self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Initialize user Oauth2 implementation."""

        super().__init__(
            hass,
            auth_domain,
            credential,
            AuthorizationServer(AUTHORIZE_URL, TOKEN_URL),
        )

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "prompt": "login",
            "prompt_missing_scopes": "true",
            "scope": " ".join(SCOPES),
        }
