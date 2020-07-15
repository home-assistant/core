"""Test the Smappee config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.smappee import config_flow
from homeassistant.components.smappee.const import (
    AUTHORIZE_URL,
    CONF_HOSTNAME,
    CONF_SERIALNUMBER,
    CONF_TITLE,
    DOMAIN,
    ENV_CLOUD,
    TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_IP_ADDRESS
from homeassistant.helpers import config_entry_oauth2_flow

from tests.async_mock import patch

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


async def test_show_user_form(hass):
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zeroconf_confirm_form(hass):
    """Test that the zeroconf confirmation form is served."""
    flow = config_flow.SmappeeFlowHandler()
    flow.hass = hass
    flow.context = {
        "source": SOURCE_ZEROCONF,
        CONF_HOSTNAME: "Smappee1006000212.local.",
        CONF_TITLE: "Smappee1006000212",
        CONF_IP_ADDRESS: "1.2.3.4",
        CONF_SERIALNUMBER: "1006000212",
    }
    result = await flow.async_step_zeroconf_confirm()

    assert flow.context["source"] == SOURCE_ZEROCONF
    assert result["description_placeholders"] == {CONF_SERIALNUMBER: "1006000212"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zeroconf_connection_error_form(
    hass, aiohttp_client, aioclient_mock
):
    """Test that the zeroconf confirmation form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "host": "1.2.3.4",
            "port": 22,
            CONF_HOSTNAME: "Smappee1006000212.local.",
            "type": "_ssh._tcp.local.",
            "name": "Smappee1006000212._ssh._tcp.local.",
            "properties": {"_raw": {}},
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "connection_error"


async def test_connection_error(hass, aiohttp_client, aioclient_mock):
    """Test we show user form on Smappee connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"host": "1.2.3.4"},
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_connection_error_empty_host(hass, aiohttp_client, aioclient_mock):
    """Test we show user form on Smappee connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"host": None},
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_no_data(hass, aiohttp_client, aioclient_mock):
    """Test we abort if zeroconf provides no data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}
    )

    assert result["reason"] == "connection_error"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zerconf_wrong_mdns(hass, aiohttp_client, aioclient_mock):
    """Test we abort if unsupported mDNS name is discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "host": "1.2.3.4",
            "port": 22,
            CONF_HOSTNAME: "example.local.",
            "type": "_ssh._tcp.local.",
            "name": "example._ssh._tcp.local.",
            "properties": {"_raw": {}},
        },
    )

    assert result["reason"] == "invalid_mdns"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_full_flow(hass, aiohttp_client, aioclient_mock):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {CONF_CLIENT_ID: CLIENT_ID, CONF_CLIENT_SECRET: CLIENT_SECRET},
            "http": {"base_url": "https://example.com"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"environment": ENV_CLOUD},
    )
    state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"]})

    assert result["url"] == (
        f"{AUTHORIZE_URL['PRODUCTION']}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL["PRODUCTION"],
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.smappee.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
