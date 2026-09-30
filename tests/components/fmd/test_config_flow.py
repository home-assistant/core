"""Test FMD config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.fmd.config_flow import (
    _normalize_artifacts,
    authenticate_and_get_artifacts,
)
from homeassistant.components.fmd.const import DEFAULT_POLLING_INTERVAL, DOMAIN
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_form(hass: HomeAssistant, mock_fmd_api: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    dummy_artifacts = {
        "base_url": "https://fmd.example.com",
        "fmd_id": "test_user",
        "access_token": "mock_access_token",
        "private_key": "MOCK_KEY",
        "password_hash": "mock_password_hash",
        "session_duration": 3600,
        "token_issued_at": 1234567890.0,
    }
    with patch(
        "homeassistant.components.fmd.config_flow.authenticate_and_get_artifacts",
        return_value=dummy_artifacts,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://fmd.example.com",
                CONF_ID: "test_user",
                CONF_PASSWORD: "test_password",
                "polling_interval": 30,
                "allow_inaccurate_locations": False,
                "use_imperial": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test_user"
    # Password should NOT be stored; artifacts should be present instead
    assert result2["data"][CONF_URL] == "https://fmd.example.com"
    assert result2["data"][CONF_ID] == "test_user"
    assert "artifacts" in result2["data"]
    assert CONF_PASSWORD not in result2["data"]
    assert result2["data"]["polling_interval"] == 30
    assert result2["data"]["allow_inaccurate_locations"] is False
    assert result2["data"]["use_imperial"] is False


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fmd.config_flow.authenticate_and_get_artifacts",
        side_effect=Exception("Authentication failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://fmd.example.com",
                CONF_ID: "test_user",
                CONF_PASSWORD: "wrong_password",
                "polling_interval": 30,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fmd.config_flow.authenticate_and_get_artifacts",
        side_effect=ConnectionError("Cannot reach server"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://invalid.example.com",
                CONF_ID: "test_user",
                CONF_PASSWORD: "test_password",
                "polling_interval": 30,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_default_values(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test default values are set correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    dummy_artifacts = {
        "base_url": "https://fmd.example.com",
        "fmd_id": "test_user",
        "access_token": "mock_access_token",
        "private_key": "MOCK_KEY",
        "password_hash": "mock_password_hash",
        "session_duration": 3600,
        "token_issued_at": 1234567890.0,
    }
    with patch(
        "homeassistant.components.fmd.config_flow.authenticate_and_get_artifacts",
        return_value=dummy_artifacts,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://fmd.example.com",
                CONF_ID: "test_user",
                CONF_PASSWORD: "test_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["data"]["polling_interval"] == DEFAULT_POLLING_INTERVAL
    assert result2["data"]["allow_inaccurate_locations"] is False
    assert result2["data"]["use_imperial"] is False


async def test_authenticate_api_error(hass: HomeAssistant) -> None:
    """Test authenticate_and_get_artifacts with API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fmd.config_flow.authenticate_and_get_artifacts",
        side_effect=TimeoutError("API timeout"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://fmd.example.com",
                CONF_ID: "test_user",
                CONF_PASSWORD: "test_password",
                "polling_interval": 30,
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_authenticate_and_get_artifacts_success(mock_fmd_api: AsyncMock) -> None:
    """Test authenticate_and_get_artifacts function directly."""
    # Prepare mock client to return one location then artifacts
    mock_fmd_api.get_locations = AsyncMock(return_value=[{"lat": 1, "lon": 2}])
    mock_artifacts = {
        "base_url": "https://fmd.example.com",
        "fmd_id": "test_user",
        "access_token": "mock_access_token",
        "private_key": "MOCK_KEY",
        "password_hash": "mock_password_hash",
        "session_duration": 3600,
        "token_issued_at": 1234567890.0,
    }
    mock_fmd_api.export_auth_artifacts = AsyncMock(return_value=mock_artifacts)
    mock_fmd_api.close = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.fmd.config_flow.FmdClient.create",
        return_value=mock_fmd_api,
    ):
        artifacts = await authenticate_and_get_artifacts(
            "https://fmd.example.com", "test_user", "test_password"
        )

    assert artifacts == mock_artifacts
    mock_fmd_api.get_locations.assert_called_once_with(1)
    mock_fmd_api.export_auth_artifacts.assert_called_once()


def test_normalize_artifacts_with_mock_object() -> None:
    """Test _normalize_artifacts with an object that has .get() but is not a dict."""

    class MockArtifacts:
        def get(self, key: str, default: Any = None) -> Any:
            data = {
                "base_url": "http://test.url",
                "fmd_id": "test_id",
                "access_token": "token",
                "private_key": "key",
                "password_hash": "hash",
            }
            return data.get(key, default)

    mock_artifacts = MockArtifacts()

    # Ensure isinstance(mock_artifacts, dict) is False
    assert not isinstance(mock_artifacts, dict)

    # Call the function
    result = _normalize_artifacts(mock_artifacts)

    # Verify result is a dict with expected keys
    assert isinstance(result, dict)
    assert result["base_url"] == "http://test.url"
    assert result["fmd_id"] == "test_id"
    assert result["access_token"] == "token"


def test_normalize_artifacts_with_list_of_tuples() -> None:
    """Test _normalize_artifacts with a list of tuples (convertible to dict)."""
    artifacts = [("base_url", "http://example.com"), ("fmd_id", "123")]
    normalized = _normalize_artifacts(artifacts)
    assert normalized == {"base_url": "http://example.com", "fmd_id": "123"}
