"""Test the Legrand Home+ Control config flow."""
import asyncio

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.homepluscontrol.const import (
    CONF_SUBSCRIPTION_KEY,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.components.homepluscontrol.conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    SUBSCRIPTION_KEY,
)


async def test_full_flow(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    valid_configuration = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "subscription_key": SUBSCRIPTION_KEY,
    }

    assert await setup.async_setup_component(
        hass,
        "homepluscontrol",
        {
            "homepluscontrol": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
            "http": {},
        },
    )
    assert hass.http.app
    result = await hass.config_entries.flow.async_init(
        "homepluscontrol", context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(  # pylint: disable=protected-access
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["step_id"] == "auth"
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

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Home+ Control"
    config_data = result["data"]
    for item in valid_configuration:
        assert item in config_data
        assert config_data[item] == valid_configuration[item]
    assert config_data["token"]["refresh_token"] == "mock-refresh-token"
    assert config_data["token"]["access_token"] == "mock-access-token"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_abort_if_entry_in_progress(hass, current_request_with_host):
    """Check flow abort when an entry is already in progress."""
    assert await setup.async_setup_component(
        hass,
        "homepluscontrol",
        {
            "homepluscontrol": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
            "http": {},
        },
    )

    # Start one flow
    result = await hass.config_entries.flow.async_init(
        "homepluscontrol", context={"source": config_entries.SOURCE_USER}
    )

    # Attempt to start another flow
    result = await hass.config_entries.flow.async_init(
        "homepluscontrol", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


async def test_abort_if_entry_exists(hass, current_request_with_host):
    """Check flow abort when an entry already exists."""
    existing_entry = MockConfigEntry(domain=DOMAIN)
    existing_entry.add_to_hass(hass)

    assert await setup.async_setup_component(
        hass,
        "homepluscontrol",
        {
            "homepluscontrol": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
            "http": {},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "homepluscontrol", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_abort_if_invalid_token(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check flow abort when the token has an invalid value."""
    assert await setup.async_setup_component(
        hass,
        "homepluscontrol",
        {
            "homepluscontrol": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
            "http": {},
        },
    )
    assert hass.http.app
    result = await hass.config_entries.flow.async_init(
        "homepluscontrol", context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(  # pylint: disable=protected-access
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["step_id"] == "auth"
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
            "expires_in": "non-integer",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "oauth_error"


async def test_flow_timeout(
    hass, aiohttp_client, aioclient_mock, current_request_with_host
):
    """Check timeout in config flow."""
    assert await setup.async_setup_component(
        hass,
        "homepluscontrol",
        {
            "homepluscontrol": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
            "http": {},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "homepluscontrol", context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(  # pylint: disable=protected-access
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["step_id"] == "auth"
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
        exc=asyncio.TimeoutError,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "oauth_error"


async def test_config_options_flow(hass):
    """Test config options flow."""
    valid_option = {
        "plant_update_interval": "301",
        "plant_topology_update_interval": "302",
        "module_status_update_interval": "303",
    }

    expected_result = {
        "plant_update_interval": "301",
        "plant_topology_update_interval": "302",
        "module_status_update_interval": "303",
    }

    hass.data[DOMAIN] = {}

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=valid_option
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    for key, value in expected_result.items():
        assert config_entry.options[key] == value


async def test_invalid_options_flow(hass):
    """Test config options flow with invalid input."""
    input_option = {
        "plant_update_interval": "7200",
        "plant_topology_update_interval": "3600",
        "module_status_update_interval": "300",
    }

    # Valid values are: 0 < int <= 86400
    invalid_values = [-1, "non-int", 0, 86401, 300000]

    hass.data[DOMAIN] = {}

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={},
        options={},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    for interval in input_option:
        for i_value in invalid_values:
            input_option[interval] = i_value

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=input_option
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        form_errors = result.get("errors", None)
        assert form_errors is not None
        assert form_errors.get(interval) == "invalid_update_interval"
