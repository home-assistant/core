"""Test the myUplink config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.myuplink.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "myuplink", context={"source": config_entries.SOURCE_USER}
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
        "&scope=WRITESYSTEM+READSYSTEM+offline_access"
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
        "homeassistant.components.myuplink.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_flow_reauth(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,
    init_integration,
    expires_at,
) -> None:
    """Test reauth step."""

    OLD_SCOPE = {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": "Fake_token",
            "scope": "READSYSTEM offline_access",
            "expires_in": 86399,
            "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
            "token_type": "Bearer",
            "expires_at": expires_at,
        },
    }

    entry = init_integration
    hass.config_entries.async_update_entry(entry, data=OLD_SCOPE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]
    assert result["flow_id"] == flows[0]["flow_id"]

    result3 = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], user_input={}
    )
    assert result3["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result3["step_id"] == "auth"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"], user_input={}
    )
    assert result4["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP_DONE
    assert result4["step_id"] == "creation"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    # assert entry.data["token"]["scope"] == "WRITESYSTEM READSYSTEM offline_access"
