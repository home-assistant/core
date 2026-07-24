"""Test the Teslemetry OAuth client registration helper."""

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.teslemetry.const import (
    DOMAIN,
    REGISTER_URL,
    SOFTWARE_ID,
    TOKEN_URL,
)
from homeassistant.components.teslemetry.oauth import async_ensure_client_credential
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .const import DCR_CLIENT_ID

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_registers_new_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a new client is dynamically registered when none exists yet."""
    assert await async_setup_component(hass, "application_credentials", {})

    await async_ensure_client_credential(hass)

    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )
    assert implementations[DOMAIN].client_id == DCR_CLIENT_ID
    register_calls = [
        call for call in aioclient_mock.mock_calls if str(call[1]) == REGISTER_URL
    ]
    assert len(register_calls) == 1
    assert register_calls[0][2] == {
        "client_name": "Home Assistant",
        "software_id": SOFTWARE_ID,
        "software_version": __version__,
    }


async def test_reuses_existing_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an already-registered client is reused instead of re-registering."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("existing-client-id", "", name="Teslemetry")
    )

    await async_ensure_client_credential(hass)

    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )
    assert implementations[DOMAIN].client_id == "existing-client-id"
    register_calls = [
        call for call in aioclient_mock.mock_calls if str(call[1]) == REGISTER_URL
    ]
    assert not register_calls


async def test_refresh_token_sends_software_metadata(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the refresh grant re-sends software_id and software_version."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_ensure_client_credential(hass)

    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )
    implementation = implementations[DOMAIN]

    aioclient_mock.post(
        TOKEN_URL,
        json={
            "refresh_token": "new_refresh_token",
            "access_token": "new_access_token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    await implementation.async_refresh_token({"refresh_token": "old_refresh_token"})

    token_calls = [
        call for call in aioclient_mock.mock_calls if str(call[1]) == TOKEN_URL
    ]
    assert len(token_calls) == 1
    assert token_calls[0][2]["grant_type"] == "refresh_token"
    assert token_calls[0][2]["software_id"] == SOFTWARE_ID
    assert token_calls[0][2]["software_version"] == __version__
