"""Test the Legrand Home+ Control config flow."""
from aiohttp import ServerTimeoutError
import pytest
import voluptuous

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.homepluscontrol.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.helpers import config_entry_oauth2_flow

from tests.async_mock import patch
from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SUBSCRIPTION_KEY = "12345678901234567890123456789012"
REDIRECT_URI = "https://example.com:8213/auth/external/callback"


async def test_full_flow(hass, aiohttp_client, aioclient_mock, current_request):
    """Check full flow."""
    valid_configuration = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "subscription_key": SUBSCRIPTION_KEY,
        "redirect_uri": REDIRECT_URI,
    }

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_init(
            "homepluscontrol", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=valid_configuration
        )

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["step_id"] == "auth"
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com:8213/auth/external/callback"
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
        "homeassistant.components.homepluscontrol.async_setup_entry", return_value=True
    ) as mock_setup:
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
    assert len(mock_setup.mock_calls) == 1


async def test_abort_if_entry_in_progress(hass):
    """Check flow abort when an entry is already in progress."""
    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_init(
            "homepluscontrol", context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_init(
            "homepluscontrol", context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_in_progress"


async def test_abort_if_entry_exists(hass):
    """Check flow abort when an entry already exists."""
    existing_entry = MockConfigEntry(domain=DOMAIN)
    existing_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_init(
            "homepluscontrol", context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_invalid_user_input(hass):
    """Check flow show form when a config value entered by the user is invalid."""
    input_configuration = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "subscription_key": "tooShort",
        "redirect_uri": REDIRECT_URI,
    }

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_init(
            "homepluscontrol", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=input_configuration
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    form_errors = result.get("errors", None)
    assert form_errors is not None
    assert form_errors.get("subscription_key") == "invalid_subscription_key"

    # Now use valid subscription key, but remove a required field -> raises voluptuous validation exception.
    input_configuration = {
        "client_id": CLIENT_ID,
        "subscription_key": SUBSCRIPTION_KEY,
        "redirect_uri": REDIRECT_URI,
    }

    with pytest.raises(
        voluptuous.error.MultipleInvalid,
        match=r".*required key not provided.*client_secret.*",
    ):
        with patch(
            "homeassistant.components.homepluscontrol.config_flow.get_url",
            return_value="https://example.com:8213",
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=input_configuration
            )


async def test_flow_timeout(hass, aiohttp_client, aioclient_mock, current_request):
    """Check full flow."""
    valid_configuration = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "subscription_key": SUBSCRIPTION_KEY,
        "redirect_uri": REDIRECT_URI,
    }

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_init(
            "homepluscontrol", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.homepluscontrol.config_flow.get_url",
        return_value="https://example.com:8213",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=valid_configuration
        )

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["step_id"] == "auth"
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com:8213/auth/external/callback"
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
        exc=ServerTimeoutError,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    print(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "oauth_error"
