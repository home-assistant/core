"""application_credentials platform for YouTube."""

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .auth_config import HinenImplementation


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    return HinenImplementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url="https://dev-knowledge.celinksmart.cn/#/auth",
            token_url="https://dev-iot-api.celinksmart.cn/iot-global/open-platforms/auth/token",
        ),
    )
