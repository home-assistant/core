"""Test the Legrand Home+ Control config flow."""
from http import HTTPStatus
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.home_plus_control.const import (
    CONF_SUBSCRIPTION_KEY,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.components.home_plus_control.conftest import (
    CLIENT_ID,
    CLIENT_SECRET,
    SUBSCRIPTION_KEY,
)


async def test_full_flow(
    hass, hass_client_no_auth, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        "home_plus_control",
        {
            "home_plus_control": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
        },
    )
    result = await hass.config_entries.flow.async_init(
        "home_plus_control", context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(  # pylint: disable=protected-access
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
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
        "homeassistant.components.home_plus_control.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home+ Control"
    config_data = result["data"]
    assert config_data["token"]["refresh_token"] == "mock-refresh-token"
    assert config_data["token"]["access_token"] == "mock-access-token"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_abort_if_entry_in_progress(hass, current_request_with_host):
    """Check flow abort when an entry is already in progress."""
    assert await setup.async_setup_component(
        hass,
        "home_plus_control",
        {
            "home_plus_control": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
        },
    )

    # Start one flow
    result = await hass.config_entries.flow.async_init(
        "home_plus_control", context={"source": config_entries.SOURCE_USER}
    )

    # Attempt to start another flow
    result = await hass.config_entries.flow.async_init(
        "home_plus_control", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_abort_if_entry_exists(hass, current_request_with_host):
    """Check flow abort when an entry already exists."""
    existing_entry = MockConfigEntry(domain=DOMAIN)
    existing_entry.add_to_hass(hass)

    assert await setup.async_setup_component(
        hass,
        "home_plus_control",
        {
            "home_plus_control": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
            "http": {},
        },
    )

    result = await hass.config_entries.flow.async_init(
        "home_plus_control", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_abort_if_invalid_token(
    hass, hass_client_no_auth, aioclient_mock, current_request_with_host
):
    """Check flow abort when the token has an invalid value."""
    assert await setup.async_setup_component(
        hass,
        "home_plus_control",
        {
            "home_plus_control": {
                CONF_CLIENT_ID: CLIENT_ID,
                CONF_CLIENT_SECRET: CLIENT_SECRET,
                CONF_SUBSCRIPTION_KEY: SUBSCRIPTION_KEY,
            },
        },
    )
    result = await hass.config_entries.flow.async_init(
        "home_plus_control", context={"source": config_entries.SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(  # pylint: disable=protected-access
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
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
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
