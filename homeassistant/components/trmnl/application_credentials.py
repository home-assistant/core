"""Application credentials platform for the TRMNL integration."""

from typing import Any, override

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import OAUTH2_AUTHORIZE, OAUTH2_SCOPES, OAUTH2_TOKEN


class TRMNLOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """TRMNL OAuth2 implementation."""

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Ask for the capabilities the integration uses."""
        return {"scope": OAUTH2_SCOPES, **super().extra_authorize_data}


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> TRMNLOAuth2Implementation:
    """Return the TRMNL OAuth2 implementation."""
    return TRMNLOAuth2Implementation(
        hass, auth_domain, credential.client_id, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
    )
