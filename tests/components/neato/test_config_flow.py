"""Test the Neato Botvac config flow."""
from pybotvac.neato import Neato

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.neato.config_flow import OAuth2FlowHandler
from homeassistant.components.neato.const import NEATO_DOMAIN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.typing import HomeAssistantType

from tests.async_mock import patch
from tests.common import MockConfigEntry
from tests.helpers.test_config_entry_oauth2_flow import local_impl  # noqa: F401

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

VENDOR = Neato()
OAUTH2_AUTHORIZE = VENDOR.auth_endpoint
OAUTH2_TOKEN = VENDOR.token_endpoint


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        "neato",
        {
            "neato": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
            "http": {"base_url": "https://example.com"},
        },
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
        "homeassistant.components.neato.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(NEATO_DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_abort_if_already_setup(hass: HomeAssistantType):
    """Test we abort if Neato is already setup."""
    entry = MockConfigEntry(
        domain=NEATO_DOMAIN,
        data={"client_id": "abcdef", "client_secret": "123456"},
        version=2,
    )
    entry.add_to_hass(hass)

    # Should fail
    result = await hass.config_entries.flow.async_init(
        "neato", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistantType):
    """Test initialization of the reauth flow."""
    MockConfigEntry(
        domain=NEATO_DOMAIN,
        data={"username": "abcdef", "password": "123456", "vendor": "neato"},
        version=1,
    ).add_to_hass(hass)

    # Should show form
    result = await hass.config_entries.flow.async_init(
        "neato", context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    # Form confirmed, init new flow
    with patch(
        "homeassistant.components.neato.config_flow.OAuth2FlowHandler.async_step_user",
        return_value={
            "description_placeholders": None,
            "flow_id": result["flow_id"],
            "handler": "neato",
            "step_id": "auth",
            "type": "external",
            "url": "https://example.com/",
        },
    ) as mock_user:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    mock_user.assert_called_once_with()


async def test_oauth_create_entry(hass: HomeAssistantType, local_impl):  # noqa: 811
    """Test migration from version 1 to version 2."""
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.flow_impl = local_impl

    MockConfigEntry(
        entry_id="my_entry",
        domain=NEATO_DOMAIN,
        data={"username": "abcdef", "password": "123456", "vendor": "neato"},
        version=1,
    ).add_to_hass(hass)

    # Update entry
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=True,
    ) as mock_reload:
        result = await flow.async_oauth_create_entry({"my": "data"})

    await hass.async_block_till_done()

    new_entry = hass.config_entries.async_get_entry("my_entry")

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert new_entry.version == 2
    assert new_entry.data == {"my": "data"}

    mock_reload.assert_called_once_with("my_entry")
