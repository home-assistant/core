# mypy: ignore-errors
"""Test the Grandstream Home __init__ module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from grandstream_home_api import DEVICE_TYPE_GDS
import pytest

from homeassistant.components.grandstream_home import (
    GrandstreamRuntimeData,
    _get_display_model,
    _setup_api,
    async_unload_entry,
)
from homeassistant.components.grandstream_home.const import CONF_DEVICE_MODEL, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


def test_get_display_model() -> None:
    """Test _get_display_model function."""
    # When product_model is provided, return it
    assert _get_display_model("gds", "GDS3710") == "GDS3710"
    # When product_model is None, return device_model
    assert _get_display_model("gds", None) == "gds"


@pytest.fixture
def mock_gds_entry():
    """Create a mock GDS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_DEVICE_MODEL: DEVICE_TYPE_GDS,
            "port": 443,
            "verify_ssl": False,
        },
        unique_id="test_gds",
    )


async def test_unload_entry(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test unload entry."""
    mock_gds_entry.add_to_hass(hass)

    # Set up runtime_data
    mock_coordinator = MagicMock()
    mock_api = MagicMock()
    mock_gds_entry.runtime_data = GrandstreamRuntimeData(
        api=mock_api,
        coordinator=mock_coordinator,
        device_info=MagicMock(),
        device_model=DEVICE_TYPE_GDS,
        product_model=None,
        unique_id="test_gds",
    )

    # Mock the unload function to return True
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ):
        result = await async_unload_entry(hass, mock_gds_entry)
    assert result is True


@pytest.mark.asyncio
async def test_setup_api_ha_control_disabled(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_api raises ConfigEntryNotReady for HA control disabled."""
    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "ha_control_disabled"),
        ),
        pytest.raises(ConfigEntryNotReady, match="Home Assistant control is disabled"),
    ):
        await _setup_api(hass, mock_gds_entry)


@pytest.mark.asyncio
async def test_setup_api_auth_failed(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_api raises ConfigEntryNotReady for auth failed."""
    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "invalid_auth"),
        ),
        pytest.raises(ConfigEntryNotReady, match="Authentication failed"),
    ):
        await _setup_api(hass, mock_gds_entry)


@pytest.mark.asyncio
async def test_setup_api_success(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_api succeeds."""
    mock_api = MagicMock()
    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(True, None),
        ),
    ):
        result = await _setup_api(hass, mock_gds_entry)
        assert result == mock_api


@pytest.mark.asyncio
async def test_setup_api_offline(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_api handles offline device."""
    mock_api = MagicMock()
    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "offline"),
        ),
    ):
        # Should return api even when offline (coordinator will handle retries)
        result = await _setup_api(hass, mock_gds_entry)
        assert result == mock_api


@pytest.mark.asyncio
async def test_setup_api_account_locked(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_api handles account locked."""
    mock_api = MagicMock()
    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "account_locked"),
        ),
    ):
        # Should return api even when account is locked (coordinator will retry)
        result = await _setup_api(hass, mock_gds_entry)
        assert result == mock_api


@pytest.mark.asyncio
async def test_setup_api_exception(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_api handles exception during login."""
    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            side_effect=OSError("Connection refused"),
        ),
        pytest.raises(ConfigEntryNotReady, match="API setup failed"),
    ):
        await _setup_api(hass, mock_gds_entry)


@pytest.mark.enable_socket
async def test_setup_entry_gds_success(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test successful setup of GDS device entry."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.device_mac = "00:0B:82:12:34:56"
    mock_api.host = "192.168.1.100"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(True, None),
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert result is True
        assert mock_gds_entry.runtime_data is not None
        assert mock_gds_entry.runtime_data.api == mock_api
        assert mock_gds_entry.runtime_data.coordinator == mock_coordinator


@pytest.mark.enable_socket
async def test_setup_entry_login_failure(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test setup handles login failure - returns False."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.device_mac = None
    mock_api.host = "192.168.1.100"

    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "invalid_auth"),
        ),
    ):
        # When auth fails, async_setup returns False
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)
        assert result is False


@pytest.mark.enable_socket
async def test_unload_entry_success(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test unloading a config entry."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.device_mac = "00:0B:82:12:34:56"
    mock_api.host = "192.168.1.100"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(True, None),
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        setup_result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)
        assert setup_result is True

        result = await hass.config_entries.async_unload(mock_gds_entry.entry_id)
        assert result is True
