"""Application credentials platform for the BLUETTI integration."""

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SSO_URL


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=f"{SSO_URL}/oauth2/grant",
        token_url=f"{SSO_URL}/oauth2/token",
    )


async def async_ensure_default_credential(hass: HomeAssistant) -> None:
    """(Re-)import the integration's built-in OAuth2 client credential.

    Home Assistant resolves a config entry's OAuth2 implementation by looking
    up this credential in Application Credentials storage. If it is ever
    missing there - lost in a partial backup restore, or an entry that was
    created without going through the config flow - every future setup of
    that entry fails with "Implementation not available" until this import
    runs again. `async_import_client_credential` is a no-op when the
    credential already exists, so this is safe to call on every config flow
    run and every integration setup.
    """
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("HomeAssistant", "SG9tZUFzc2lzdGFudA=="),
    )
