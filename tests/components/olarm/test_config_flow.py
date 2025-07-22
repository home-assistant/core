"""Test the Olarm config flow."""

from unittest.mock import AsyncMock, patch

from olarmflowclient import OlarmFlowClientApiError
import pytest

from homeassistant import config_entries
from homeassistant.components.olarm.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .const import MOCK_DEVICES_RESPONSE

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
    ) as mock_olarm_client:
        # Mock the get_devices method to be async
        mock_client_instance = AsyncMock()
        mock_client_instance.get_devices = AsyncMock(return_value=MOCK_DEVICES_RESPONSE)
        mock_olarm_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should now be at device selection step
        assert result2.get("type") is FlowResultType.FORM
        assert result2.get("step_id") == "device"

        # Mock the setup components to prevent network calls during entry creation
        with (
            patch(
                "homeassistant.components.olarm.OlarmDataUpdateCoordinator.async_config_entry_first_refresh"
            ),
            patch("homeassistant.components.olarm.mqtt.OlarmFlowClientMQTT.init_mqtt"),
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
    ) as mock_olarm_client:
        # Mock API error
        mock_client_instance = AsyncMock()
        mock_client_instance.get_devices = AsyncMock(
            side_effect=OlarmFlowClientApiError("API Error")
        )
        mock_olarm_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("errors", {}).get("base") == "invalid_auth"


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
    ) as mock_olarm_client:
        # Mock empty devices response
        mock_client_instance = AsyncMock()
        mock_client_instance.get_devices = AsyncMock(
            return_value={
                "userId": "test-user",
                "data": None,
            }
        )
        mock_olarm_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2.get("type") == FlowResultType.ABORT
        assert result2.get("reason") == "no_devices_found"
