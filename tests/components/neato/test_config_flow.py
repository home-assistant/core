"""Test the Neato Botvac config flow."""
from unittest.mock import patch

from pybotvac.neato import Neato

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.neato.const import NEATO_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

VENDOR = Neato()
OAUTH2_AUTHORIZE = VENDOR.auth_endpoint
OAUTH2_TOKEN = VENDOR.token_endpoint


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Check full flow."""
    assert await setup.async_setup_component(hass, "neato", {})
    await async_import_client_credential(
        hass, NEATO_DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )

    result = await hass.config_entries.flow.async_init(
        "neato", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&client_secret={CLIENT_SECRET}"
        "&scope=public_profile+control_robots+maps"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.neato.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(NEATO_DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if Neato is already setup."""
    entry = MockConfigEntry(
        domain=NEATO_DOMAIN,
        data={"auth_implementation": "neato", "token": {"some": "data"}},
    )
    entry.add_to_hass(hass)

    # Should fail
    result = await hass.config_entries.flow.async_init(
        "neato", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Test initialization of the reauth flow."""
    assert await setup.async_setup_component(hass, "neato", {})
    await async_import_client_credential(
        hass, NEATO_DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )

    MockConfigEntry(
        entry_id="my_entry",
        domain=NEATO_DOMAIN,
        data={"username": "abcdef", "password": "123456", "vendor": "neato"},
    ).add_to_hass(hass)

    # Should show form
    result = await hass.config_entries.flow.async_init(
        "neato", context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Confirm reauth flow
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    # Update entry
    with patch(
        "homeassistant.components.neato.async_setup_entry", return_value=True
    ) as mock_setup:
        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"])
        await hass.async_block_till_done()

    new_entry = hass.config_entries.async_get_entry("my_entry")

    assert result3["type"] == data_entry_flow.FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert new_entry.state == config_entries.ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(NEATO_DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
