"""Test the Netatmo config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from pyatmo.const import ALL_SCOPES

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.netatmo import config_flow
from homeassistant.components.netatmo.const import (
    CONF_NEW_AREA,
    CONF_WEATHER_AREAS,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import CLIENT_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

VALID_CONFIG = {}


async def test_abort_if_existing_entry(hass: HomeAssistant) -> None:
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    flow = config_flow.NetatmoFlowHandler()
    flow.hass = hass

    result = await hass.config_entries.flow.async_init(
        "netatmo", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

    result = await hass.config_entries.flow.async_init(
        "netatmo",
        context={"source": config_entries.SOURCE_HOMEKIT},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.5"),
            ip_addresses=[ip_address("192.168.1.5")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={zeroconf.ATTR_PROPERTIES_ID: "aa:bb:cc:dd:ee:ff"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Check full flow."""

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

    scope = "+".join(sorted(ALL_SCOPES))

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
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
        "homeassistant.components.netatmo.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_option_flow(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NEW_AREA: "Home"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "public_weather"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    for k, v in expected_result.items():
        assert config_entry.options[CONF_WEATHER_AREAS]["Home"][k] == v


async def test_option_flow_wrong_coordinates(hass: HomeAssistant) -> None:
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_NEW_AREA: "Home"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "public_weather"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "public_weather_areas"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    for k, v in expected_result.items():
        assert config_entry.options[CONF_WEATHER_AREAS]["Home"][k] == v


async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
) -> None:
    """Test initialization of the reauth flow."""

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

    scope = "+".join(sorted(ALL_SCOPES))

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope={scope}"
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
        "homeassistant.components.netatmo.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    new_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert new_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    # Should show form
    result = await hass.config_entries.flow.async_init(
        "netatmo", context={"source": config_entries.SOURCE_REAUTH}
    )
    assert result["type"] is FlowResultType.FORM
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
        "homeassistant.components.netatmo.async_setup_entry", return_value=True
    ) as mock_setup:
        result3 = await hass.config_entries.flow.async_configure(result2["flow_id"])
        await hass.async_block_till_done()

    new_entry2 = hass.config_entries.async_entries(DOMAIN)[0]

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert new_entry2.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
