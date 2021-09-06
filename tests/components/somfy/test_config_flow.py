"""Tests for the Somfy config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.somfy import DOMAIN
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry

CLIENT_ID_VALUE = "1234"
CLIENT_SECRET_VALUE = "5678"


async def test_abort_if_no_configuration(hass):
    """Check flow abort when no configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_abort_if_existing_entry(hass):
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_full_flow(
    hass, hass_client_no_auth, aioclient_mock, current_request_with_host
):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_CLIENT_ID: CLIENT_ID_VALUE,
                CONF_CLIENT_SECRET: CLIENT_SECRET_VALUE,
            }
        },
    )

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

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == (
        "https://accounts.somfy.com/oauth/oauth/v2/auth"
        f"?response_type=code&client_id={CLIENT_ID_VALUE}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        "https://accounts.somfy.com/oauth/oauth/v2/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.somfy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == DOMAIN

    result["data"]["token"].pop("expires_at")
    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_authorization_timeout(hass, current_request_with_host):
    """Check Somfy authorization timeout."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_CLIENT_ID: CLIENT_ID_VALUE,
                CONF_CLIENT_SECRET: CLIENT_SECRET_VALUE,
            }
        },
    )

    with patch(
        "homeassistant.components.somfy.config_entry_oauth2_flow."
        "LocalOAuth2Implementation.async_generate_authorize_url",
        side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "authorize_url_timeout"
