"""Test the Watts Vision config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.watts.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the full OAuth2 config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "url" in result
    assert OAUTH2_AUTHORIZE in result["url"]
    assert "response_type=code" in result["url"]
    assert "scope=" in result["url"]

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
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    with (
        patch(
            "homeassistant.components.watts.config_flow.WattsVisionAuth.extract_user_id_from_token",
            return_value="user123",
        ),
        patch(
            "homeassistant.components.watts.WattsVisionCoordinator.async_config_entry_first_refresh",
            return_value=AsyncMock(),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Watts Vision +"
        assert "token" in result2["data"]
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_invalid_token_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the OAuth2 config flow with invalid token."""
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
            "access_token": "invalid-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    with patch(
        "homeassistant.components.watts.config_flow.WattsVisionAuth.extract_user_id_from_token",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "invalid_token"


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

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={"error": "invalid_grant"},
    )

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_timeout(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth timeout handling."""
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

    aioclient_mock.post(OAUTH2_TOKEN, exc=TimeoutError())

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "oauth_timeout"


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_invalid_response(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth invalid response handling."""
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

    aioclient_mock.post(OAUTH2_TOKEN, status=500, text="invalid json")

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "oauth_failed"


@pytest.mark.usefixtures("current_request_with_host")
async def test_unique_config_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that duplicate config entries are not allowed."""
    mock_entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Watts Vision +",
        data={"token": {"refresh_token": "mock-refresh-token"}},
        source=config_entries.SOURCE_USER,
        unique_id="watts_vision_user123",
        entry_id="test_entry",
        options={},
        discovery_keys={},
        subentries_data={},
    )
    await hass.config_entries.async_add(mock_entry)

    with patch(
        "homeassistant.components.watts.config_flow.WattsVisionAuth.extract_user_id_from_token",
        return_value="user123",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        if result["type"] is FlowResultType.EXTERNAL_STEP:
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
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )

            result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_unique_config_entry_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a full flow after an existing entry aborts due to uniqueness."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

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
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    with (
        patch(
            "homeassistant.components.watts.config_flow.WattsVisionAuth.extract_user_id_from_token",
            return_value="user123",
        ),
        patch(
            "homeassistant.components.watts.WattsVisionCoordinator.async_config_entry_first_refresh",
            return_value=AsyncMock(),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result3["type"] is FlowResultType.EXTERNAL_STEP

    state2 = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result3["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    resp2 = await client.get(f"/auth/external/callback?code=efgh&state={state2}")
    assert resp2.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token-2",
            "access_token": "mock-access-token-2",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    with patch(
        "homeassistant.components.watts.config_flow.WattsVisionAuth.extract_user_id_from_token",
        return_value="user123",
    ):
        result4 = await hass.config_entries.flow.async_configure(result3["flow_id"])
        assert result4["type"] is FlowResultType.ABORT
        assert result4["reason"] == "already_configured"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
