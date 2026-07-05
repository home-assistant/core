"""Test the Teslemetry OAuth client registration helper."""

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.teslemetry.const import DOMAIN, REGISTER_URL
from homeassistant.components.teslemetry.oauth import async_ensure_client_credential
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
