"""application_credentials platform the Weheat integration."""

from typing import Any

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2Implementation,
)

from .const import API_SCOPE, OAUTH2_AUTHORIZE, OAUTH2_TOKEN


class WeheatOAuth2Implementation(LocalOAuth2Implementation):
    """Weheat variant of LocalOAuth2Implementation to support a keycloak specific error message."""

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": API_SCOPE}


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return a custom auth implementation."""
    return WeheatOAuth2Implementation(
        hass,
        domain=auth_domain,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
