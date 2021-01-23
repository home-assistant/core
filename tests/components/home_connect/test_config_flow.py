"""Test the Home Connect config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.home_connect.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        "home_connect",
        {
            "home_connect": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
            },
            "http": {"base_url": "https://example.com"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "home_connect", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await aiohttp_client(hass.http.app)
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
        "homeassistant.components.home_connect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
