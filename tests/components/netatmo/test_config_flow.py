"""Test the Netatmo config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.netatmo import config_flow
from homeassistant.components.netatmo.const import (
    CONF_NEW_AREA,
    CONF_WEATHER_AREAS,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from tests.async_mock import patch
from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

VALID_CONFIG = {}


async def test_abort_if_existing_entry(hass):
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    flow = config_flow.NetatmoFlowHandler()
    flow.hass = hass

    result = await hass.config_entries.flow.async_init(
        "netatmo", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"

    result = await hass.config_entries.flow.async_init(
        "netatmo",
        context={"source": "homekit"},
        data={"host": "0.0.0.0", "properties": {"id": "aa:bb:cc:dd:ee:ff"}},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        "netatmo",
        {
            "netatmo": {CONF_CLIENT_ID: CLIENT_ID, CONF_CLIENT_SECRET: CLIENT_SECRET},
            "http": {"base_url": "https://example.com"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "netatmo", context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    scope = "+".join(
        [
            "access_camera",
            "access_presence",
            "read_camera",
            "read_homecoach",
            "read_presence",
            "read_smokedetector",
            "read_station",
            "read_thermostat",
            "write_camera",
            "write_presence",
            "write_thermostat",
        ]
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
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
        "homeassistant.components.netatmo.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_option_flow(hass):
    """Test config flow options."""
    valid_option = {
        "lat_ne": 32.91336,
        "lon_ne": -117.187429,
        "lat_sw": 32.83336,
        "lon_sw": -117.26743,
        "show_on_map": False,
        "area_name": "Home",
        "mode": "avg",
    }

    expected_result = {
        "lat_ne": 32.9133601,
        "lon_ne": -117.1874289,
        "lat_sw": 32.8333601,
        "lon_sw": -117.26742990000001,
        "show_on_map": False,
        "area_name": "Home",
        "mode": "avg",
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=VALID_CONFIG,
        options={},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NEW_AREA: "Home"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "public_weather"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    for k, v in expected_result.items():
        assert config_entry.options[CONF_WEATHER_AREAS]["Home"][k] == v


async def test_option_flow_wrong_coordinates(hass):
    """Test config flow options with mixed up coordinates."""
    valid_option = {
        "lat_ne": 32.1234567,
        "lon_ne": -117.2345678,
        "lat_sw": 32.2345678,
        "lon_sw": -117.1234567,
        "show_on_map": False,
        "area_name": "Home",
        "mode": "avg",
    }

    expected_result = {
        "lat_ne": 32.2345678,
        "lon_ne": -117.1234567,
        "lat_sw": 32.1234567,
        "lon_sw": -117.2345678,
        "show_on_map": False,
        "area_name": "Home",
        "mode": "avg",
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=VALID_CONFIG,
        options={},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NEW_AREA: "Home"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "public_weather"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    for k, v in expected_result.items():
        assert config_entry.options[CONF_WEATHER_AREAS]["Home"][k] == v
