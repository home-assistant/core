# mypy: ignore-errors
"""Test the Grandstream Home __init__ module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from grandstream_home_api import DEVICE_TYPE_GDS
import pytest

from homeassistant.components.grandstream_home import (
    GrandstreamRuntimeData,
    _create_device_info,
    _get_display_model,
    _setup_api,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.grandstream_home.const import CONF_DEVICE_MODEL, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


def test_get_display_model() -> None:
    """Test _get_display_model function."""
    assert _get_display_model("gds", "GDS3710") == "GDS3710"
    assert _get_display_model("gds", None) == "gds"


@pytest.fixture
def mock_gds_entry():
    """Create a mock GDS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_USERNAME: "gdsha",
            CONF_PASSWORD: "password",
            CONF_DEVICE_MODEL: DEVICE_TYPE_GDS,
            "port": 443,
            "verify_ssl": False,
        },
        unique_id="AA:BB:CC:DD:EE:FF",
    )


async def test_unload_entry(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test unload entry."""
    mock_gds_entry.add_to_hass(hass)

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
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(False, "auth_failed"),
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
        result = await _setup_api(hass, mock_gds_entry)
        assert result == mock_api


@pytest.mark.asyncio
async def test_setup_api_exception(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _setup_api handles exception during login."""
    with (
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            side_effect=OSError("Connection refused"),
        ),
        pytest.raises(ConfigEntryNotReady, match="API setup failed"),
    ):
        await _setup_api(hass, mock_gds_entry)


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
        result = await _setup_api(hass, mock_gds_entry)
        assert result == mock_api


def test_create_device_info_with_ip_and_mac() -> None:
    """Test _create_device_info with IP and MAC."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "Test Device"},
    )

    device_info = _create_device_info(
        entry=entry,
        unique_id="test_id",
        device_model="gds",
        product_model="GDS3710",
        ip_address="192.168.1.100",
        mac_address="AA:BB:CC:DD:EE:FF",
        firmware_version="1.0.0",
    )

    assert device_info["name"] == "Test Device"
    assert device_info["model"] == "GDS3710 (IP: 192.168.1.100)"
    assert device_info["sw_version"] == "1.0.0"
    assert ("mac", "aa:bb:cc:dd:ee:ff") in device_info["connections"]


def test_create_device_info_without_ip() -> None:
    """Test _create_device_info without IP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "Test Device"},
    )

    device_info = _create_device_info(
        entry=entry,
        unique_id="test_id",
        device_model="gds",
        product_model="GDS3710",
        ip_address=None,
        mac_address=None,
        firmware_version=None,
    )

    assert device_info["name"] == "Test Device"
    assert device_info["model"] == "GDS3710"
    assert device_info["sw_version"] == "unknown"
    assert len(device_info["connections"]) == 0


@pytest.mark.asyncio
async def test_async_setup_entry_full(hass: HomeAssistant) -> None:
    """Test full async_setup_entry flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_USERNAME: "gdsha",
            CONF_PASSWORD: "password",
            CONF_DEVICE_MODEL: DEVICE_TYPE_GDS,
            "port": 443,
            "verify_ssl": False,
        },
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.host = "192.168.1.100"
    mock_api.device_mac = "AA:BB:CC:DD:EE:FF"

    async def mock_refresh():
        pass

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = mock_refresh

    with (
        patch(
            "homeassistant.components.grandstream_home._setup_api",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ),
    ):
        result = await async_setup_entry(hass, entry)
        assert result is True
        assert entry.runtime_data is not None
        assert entry.runtime_data.api == mock_api
        assert entry.runtime_data.coordinator == mock_coordinator


@pytest.mark.asyncio
async def test_async_setup_entry_no_unique_id(hass: HomeAssistant) -> None:
    """Test async_setup_entry with missing unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test GDS",
            CONF_USERNAME: "gdsha",
            CONF_PASSWORD: "password",
            CONF_DEVICE_MODEL: DEVICE_TYPE_GDS,
            "port": 443,
            "verify_ssl": False,
        },
        unique_id=None,
    )
    entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.host = "192.168.1.100"
    mock_api.device_mac = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "homeassistant.components.grandstream_home._setup_api",
            return_value=mock_api,
        ),
        pytest.raises(ConfigEntryNotReady, match="Config entry missing unique_id"),
    ):
        await async_setup_entry(hass, entry)
