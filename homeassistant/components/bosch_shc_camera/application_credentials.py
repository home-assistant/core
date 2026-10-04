"""Application credentials platform for Bosch Smart Home Camera."""

import base64
from typing import override

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)

OAUTH2_AUTHORIZE = (
    "https://smarthome.authz.bosch.com"
    "/auth/realms/home_auth_provider/protocol/openid-connect/auth"
)
OAUTH2_TOKEN = (
    "https://smarthome.authz.bosch.com"
    "/auth/realms/home_auth_provider/protocol/openid-connect/token"
)
OAUTH2_CLIENT_ID = "oss_residential_app"
# Shared public client credential, not a per-user secret.
OAUTH2_CLIENT_SECRET = base64.b64decode(
    "RjFqWnpzRzVOdHc3eDJWVmM4SjZxZ3NuaXNNT2ZhWmc="
).decode()
OAUTH2_SCOPES = "email offline_access profile openid"


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return the auth implementation."""
    return BoschCameraOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
        credential.client_secret,
    )


class BoschCameraOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """OAuth2 implementation with PKCE and the scopes Bosch requires."""

    @property
    @override
    def name(self) -> str:
        """Name of the implementation, used as the config entry title."""
        return "Bosch Smart Home Camera"

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return super().extra_authorize_data | {"scope": OAUTH2_SCOPES}
