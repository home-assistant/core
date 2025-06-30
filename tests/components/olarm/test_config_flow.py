"""Test the Olarm config flow."""

# pylint: disable=line-too-long
from unittest.mock import patch

from olarmflowclient import OlarmFlowClientApiError
import pytest

from homeassistant import config_entries
from homeassistant.components.olarm.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .const import MOCK_DEVICES_RESPONSE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
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

    # Check that URL contains the OAuth authorize endpoint
    assert OAUTH2_AUTHORIZE in result.get("url", "")
    assert "response_type=code" in result.get("url", "")

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
        "homeassistant.components.olarm.config_flow.OlarmFlowClient"
    ) as mock_olarm_connect:
        # Mock the get_devices method
        async def mock_get_devices():
            return MOCK_DEVICES_RESPONSE

        mock_olarm_connect.return_value.get_devices = mock_get_devices

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should now be at device selection step
        assert result2.get("type") is FlowResultType.FORM
        assert result2.get("step_id") == "device"

        # Mock the coordinator methods to prevent network calls during setup
        with (
            patch(
                "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.get_device"
            ),
            patch(
                "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.init_mqtt"
            ),
        ):
            # Complete the device selection
            result3 = await hass.config_entries.flow.async_configure(
                result2["flow_id"],
                {
                    "select_device": "123cf304-1dcf-48c6-b79b-4ce4640e3def",
                    "load_zones_bypass": False,
                },
            )

            assert result3.get("type") is FlowResultType.CREATE_ENTRY
            assert result3.get("title") == "Olarm Integration"
            assert (
                result3.get("data", {}).get("device_id")
                == "123cf304-1dcf-48c6-b79b-4ce4640e3def"
            )
            assert (
                result3.get("data", {}).get("user_id")
                == "abcd4ffb-8131-4de0-9416-a89abde63def"
            )
            assert result3.get("data", {}).get("load_zones_bypass_entities") is False

            # Check that a config entry was created
            assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth error handling."""
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

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    # Mock failed OAuth (no access token)
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "error": "invalid_grant",
        },
    )

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_api_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test API error when fetching devices."""
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

    with patch(
        "homeassistant.components.olarm.config_flow.OlarmFlowClient"
    ) as mock_olarm_connect:
        # Mock API error
        mock_olarm_connect.return_value.get_devices.side_effect = (
            OlarmFlowClientApiError("API Error")
        )

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2.get("type") == "form"
        assert (result2.get("errors") or {}).get("base") == "invalid_auth"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_devices_found(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test when no devices are found."""
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

    with patch(
        "homeassistant.components.olarm.config_flow.OlarmFlowClient"
    ) as mock_olarm_connect:
        # Mock empty devices response
        async def mock_get_devices():
            return {
                "userId": "test-user",
                "data": None,
            }

        mock_olarm_connect.return_value.get_devices = mock_get_devices

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2.get("type") == "abort"
        assert result2.get("reason") == "no_devices_found"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthentication flow."""
    # First create an existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123cf304-1dcf-48c6-b79b-4ce4640e3def",
        data={
            "user_id": "existing-user-id",
            "device_id": "123cf304-1dcf-48c6-b79b-4ce4640e3def",
            "load_zones_bypass_entities": False,
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "expires_at": 1234567890,
            },
        },
    )
    existing_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": existing_entry.entry_id},
    )

    # Should show reauth confirmation form first
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    # Submit the confirmation form to proceed to OAuth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Now should be at external step for OAuth
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    assert OAUTH2_AUTHORIZE in result.get("url", "")

    # Simulate OAuth callback
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

    # Mock successful token refresh
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.olarm.config_flow.OlarmFlowClient"
    ) as mock_olarm_connect:
        # Mock the get_devices method to return same devices
        async def mock_get_devices():
            return MOCK_DEVICES_RESPONSE

        mock_olarm_connect.return_value.get_devices = mock_get_devices

        # Mock integration setup that happens after reauth
        with (
            patch(
                "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.get_device"
            ),
            patch(
                "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.init_mqtt"
            ),
        ):
            # Complete the reauth flow
            result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should abort with reauth_successful
        assert result2.get("type") == "abort"
        assert result2.get("reason") == "reauth_successful"

        # Check that the config entry was updated with new tokens
        updated_entry = hass.config_entries.async_get_entry(existing_entry.entry_id)
        assert updated_entry is not None
        assert updated_entry.data["token"]["access_token"] == "new-access-token"
        assert updated_entry.data["token"]["refresh_token"] == "new-refresh-token"
        # Other data should remain the same
        assert updated_entry.data["device_id"] == "123cf304-1dcf-48c6-b79b-4ce4640e3def"
        # User ID should be updated from API response
        assert updated_entry.data["user_id"] == "abcd4ffb-8131-4de0-9416-a89abde63def"


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_flow_auth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauthentication flow with authentication error."""
    # First create an existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123cf304-1dcf-48c6-b79b-4ce4640e3def",
        data={
            "user_id": "existing-user-id",
            "device_id": "123cf304-1dcf-48c6-b79b-4ce4640e3def",
            "load_zones_bypass_entities": False,
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
                "expires_at": 1234567890,
            },
        },
    )
    existing_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": existing_entry.entry_id},
    )

    # Should show reauth confirmation form first
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    # Submit the confirmation form to proceed to OAuth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Now should be at external step for OAuth
    assert result.get("type") is FlowResultType.EXTERNAL_STEP

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

    # Mock failed OAuth
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.olarm.config_flow.OlarmFlowClient"
    ) as mock_olarm_connect:
        # Mock API error during reauth
        mock_olarm_connect.return_value.get_devices.side_effect = (
            OlarmFlowClientApiError("401 Unauthorized")
        )

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should show form with error
        assert result2.get("type") == "form"
        assert (result2.get("errors") or {}).get("base") == "invalid_auth"
