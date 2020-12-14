"""Test the Google Nest Device Access config flow."""

from homeassistant import config_entries, setup
from homeassistant.components.nest.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from .common import CONFIG_ENTRY_DATA, MockConfigEntry

from tests.async_mock import patch

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
PROJECT_ID = "project-id-4321"
SUBSCRIBER_ID = "subscriber-id-9876"

CONFIG = {
    DOMAIN: {
        "project_id": PROJECT_ID,
        "subscriber_id": SUBSCRIBER_ID,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
    },
    "http": {"base_url": "https://example.com"},
}


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    oauth_authorize = OAUTH2_AUTHORIZE.format(project_id=PROJECT_ID)
    assert result["url"] == (
        f"{oauth_authorize}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=https://www.googleapis.com/auth/sdm.service"
        "+https://www.googleapis.com/auth/pubsub"
        "&access_type=offline&prompt=consent"
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
        "homeassistant.components.nest.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_reauth(hass, aiohttp_client, aioclient_mock, current_request_with_host):
    """Test Nest reauthentication."""

    assert await setup.async_setup_component(hass, DOMAIN, CONFIG)

    old_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    old_entry.add_to_hass(hass)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=old_entry.data
    )

    # Requires a reconfigure step back at the first step (user)
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "user"
