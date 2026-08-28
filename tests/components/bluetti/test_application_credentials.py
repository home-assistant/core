"""Tests for application_credentials.py."""

from homeassistant.components import application_credentials
from homeassistant.components.bluetti.application_credentials import (
    async_ensure_default_credential,
    async_get_authorization_server,
)
from homeassistant.components.bluetti.const import DOMAIN, SSO_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_async_get_authorization_server(hass: HomeAssistant) -> None:
    """Async get authorization server."""
    server = await async_get_authorization_server(hass)

    assert server.authorize_url == f"{SSO_URL}/oauth2/grant"
    assert server.token_url == f"{SSO_URL}/oauth2/token"


def _stored_credential(hass: HomeAssistant):
    collection = hass.data[application_credentials.DATA_COMPONENT]
    return collection.async_client_credentials(DOMAIN).get(DOMAIN)


async def test_async_ensure_default_credential_imports_it(hass: HomeAssistant) -> None:
    """Async ensure default credential imports it."""
    await async_setup_component(hass, "application_credentials", {})

    await async_ensure_default_credential(hass)

    credential = _stored_credential(hass)
    assert credential is not None
    assert credential.client_id == "HomeAssistant"


async def test_async_ensure_default_credential_is_idempotent(
    hass: HomeAssistant,
) -> None:
    """Async ensure default credential is idempotent."""
    # A missing credential (e.g. lost in a partial backup restore) must be
    # safe to re-import on every setup attempt, not just the first one.
    await async_setup_component(hass, "application_credentials", {})

    await async_ensure_default_credential(hass)
    await async_ensure_default_credential(hass)

    collection = hass.data[application_credentials.DATA_COMPONENT]
    assert len(collection.async_client_credentials(DOMAIN)) == 1
