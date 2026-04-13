# mypy: ignore-errors
"""Test the Grandstream Home __init__ module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.grandstream_home import (
    GrandstreamRuntimeData,
    _attempt_api_login,
    _setup_api_with_error_handling,
    _setup_device,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.grandstream_home.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


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
            CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
            "port": 443,
            "verify_ssl": False,
        },
        unique_id="test_gds",
    )


@pytest.fixture
def mock_gns_entry():
    """Create a mock GNS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.101",
            CONF_NAME: "Test GNS",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_DEVICE_TYPE: DEVICE_TYPE_GNS_NAS,
            "port": 5001,
            "verify_ssl": False,
        },
        unique_id="test_gns",
    )


async def test_unload_entry(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test unload entry."""
    mock_gds_entry.add_to_hass(hass)

    # Set up runtime_data
    mock_coordinator = MagicMock()
    mock_device = MagicMock()
    mock_api = MagicMock()
    mock_gds_entry.runtime_data = GrandstreamRuntimeData(
        api=mock_api,
        coordinator=mock_coordinator,
        device=mock_device,
        device_type=DEVICE_TYPE_GDS,
        device_model=DEVICE_TYPE_GDS,
        product_model=None,
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
async def test_attempt_api_login_ha_control_disabled(hass: HomeAssistant) -> None:
    """Test _attempt_api_login raises HA control disabled when login fails and HA control is disabled."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}
    api = MagicMock()
    api.login.return_value = False
    api.is_ha_control_enabled = False

    with pytest.raises(
        ConfigEntryAuthFailed, match="Home Assistant control is disabled"
    ):
        await _attempt_api_login(hass, api)


@pytest.mark.asyncio
async def test_attempt_api_login_auth_failed(hass: HomeAssistant) -> None:
    """Test _attempt_api_login raises auth failed when login returns False."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}
    api = MagicMock()
    api.login.return_value = False
    del api.is_ha_control_enabled
    del api._account_locked

    with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
        await _attempt_api_login(hass, api)


@pytest.mark.asyncio
async def test_attempt_api_login_success(hass: HomeAssistant) -> None:
    """Test _attempt_api_login succeeds when login returns True."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}
    api = MagicMock()
    api.login.return_value = True

    # Should not raise
    await _attempt_api_login(hass, api)


@pytest.mark.asyncio
async def test_setup_device_with_no_unique_id(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_device handles entry with no unique_id."""
    test_entry = MagicMock()
    test_entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "Test GDS",
        CONF_DEVICE_TYPE: DEVICE_TYPE_GDS,
        "port": 80,
    }
    test_entry.entry_id = "test_entry_id"
    test_entry.unique_id = None

    mock_api = MagicMock()
    mock_api.host = "192.168.1.100"
    mock_api.device_mac = "AA:BB:CC:DD:EE:FF"

    device = await _setup_device(hass, test_entry, DEVICE_TYPE_GDS, mock_api)
    assert device is not None


@pytest.mark.asyncio
async def test_async_setup_entry_re_raises_auth_failed(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test async_setup_entry re-raises ConfigEntryAuthFailed."""
    mock_gds_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.grandstream_home._setup_api_with_error_handling",
            side_effect=ConfigEntryAuthFailed("Auth failed"),
        ),
        pytest.raises(ConfigEntryAuthFailed, match="Auth failed"),
    ):
        await async_setup_entry(hass, mock_gds_entry)


@pytest.mark.asyncio
async def test_setup_api_with_error_handling_os_error(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_api_with_error_handling handles OSError."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}

    with (
        patch(
            "homeassistant.components.grandstream_home._setup_api",
            side_effect=OSError("Connection error"),
        ),
        pytest.raises(ConfigEntryNotReady, match="API setup failed"),
    ):
        await _setup_api_with_error_handling(hass, mock_gds_entry, DEVICE_TYPE_GDS)


@pytest.mark.enable_socket
async def test_setup_entry_gds_success(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test successful setup of GDS device entry."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
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
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert result is True
        assert mock_gds_entry.runtime_data is not None
        assert mock_gds_entry.runtime_data.api == mock_api
        assert mock_gds_entry.runtime_data.coordinator == mock_coordinator
        assert mock_api.login.called


@pytest.mark.enable_socket
async def test_setup_entry_gns_success(hass: HomeAssistant, mock_gns_entry) -> None:
    """Test successful setup of GNS device entry."""
    mock_gns_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "00:0B:82:12:34:57"
    mock_api.host = "192.168.1.101"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        result = await hass.config_entries.async_setup(mock_gns_entry.entry_id)

        assert result is True
        assert mock_gns_entry.runtime_data is not None
        assert mock_gns_entry.runtime_data.api == mock_api
        assert mock_api.login.called


@pytest.mark.enable_socket
async def test_setup_entry_login_failure(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test setup continues even when login fails."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = False
    mock_api.device_mac = None
    mock_api.host = "192.168.1.100"
    del mock_api.is_ha_control_enabled

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert result is True
        assert mock_api.login.called


@pytest.mark.enable_socket
async def test_unload_entry_success(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test unloading a config entry."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
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
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        setup_result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)
        assert setup_result is True

        result = await hass.config_entries.async_unload(mock_gds_entry.entry_id)
        assert result is True


@pytest.mark.enable_socket
async def test_setup_entry_stores_runtime_data(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test that setup stores correct data in runtime_data."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
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
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert mock_gds_entry.runtime_data is not None
        assert isinstance(mock_gds_entry.runtime_data, GrandstreamRuntimeData)
        assert mock_gds_entry.runtime_data.api == mock_api
        assert mock_gds_entry.runtime_data.coordinator == mock_coordinator
        assert mock_gds_entry.runtime_data.device_type == DEVICE_TYPE_GDS


@pytest.mark.asyncio
async def test_setup_device_without_api_host(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_device when API has no host attribute (covers line 146)."""
    mock_gds_entry.add_to_hass(hass)

    # Create mock API without host attribute
    mock_api = MagicMock()
    mock_api.login.return_value = True
    # Remove host attribute to trigger the else branch
    del mock_api.host

    device = await _setup_device(hass, mock_gds_entry, DEVICE_TYPE_GDS, mock_api)
    assert device is not None
    # Device should get IP from entry.data
    assert device.ip_address == mock_gds_entry.data["host"]


@pytest.mark.asyncio
async def test_setup_device_with_none_api(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_device when API is None (covers line 146)."""
    mock_gds_entry.add_to_hass(hass)

    device = await _setup_device(hass, mock_gds_entry, DEVICE_TYPE_GDS, None)
    assert device is not None
    # Device should get IP from entry.data
    assert device.ip_address == mock_gds_entry.data["host"]
