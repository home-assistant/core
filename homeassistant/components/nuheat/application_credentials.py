"""Application credentials platform for NuHeat."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)

from .const import AUTHORIZE_URL, TOKEN_URL


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return the NuHeat OAuth implementation for registered credentials."""
    return LocalOAuth2ImplementationWithPkce(
        hass,
        auth_domain,
        credential.client_id,
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
        client_secret=credential.client_secret,
        code_verifier_length=128,
    )


async def async_get_description_placeholders(
    hass: HomeAssistant,
) -> dict[str, str]:
    """Return the authorization server documentation placeholder."""
    return {"docs_url": "https://api.nam.mynuheat.com/"}
