"""Application credentials platform for the Dropbox integration."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)

from .const import OAUTH2_AUTHORIZE, OAUTH2_SCOPES, OAUTH2_TOKEN


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return custom auth implementation."""
    return DropboxOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
        credential.client_secret,
    )


class DropboxOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Custom Dropbox OAuth2 implementation to add the necessary authorize url parameters."""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        data: dict = {
            "token_access_type": "offline",
            "scope": " ".join(OAUTH2_SCOPES),
        }
        data.update(super().extra_authorize_data)
        return data
