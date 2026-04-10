# mypy: ignore-errors
"""Test the Grandstream Home __init__ module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.grandstream_home import (
    _attempt_api_login,
    _create_api_instance,
    _extract_mac_address,
    _handle_existing_device,
    _raise_auth_failed,
    _raise_ha_control_disabled,
    _set_device_network_info,
    _setup_api,
    _setup_api_with_error_handling,
    _setup_device,
    _update_device_info_from_api,
    _update_device_name,
    _update_firmware_version,
    _update_stored_data,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.grandstream_home.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)
from homeassistant.components.grandstream_home.error import (
    GrandstreamHAControlDisabledError,
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
            "use_https": True,
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
            "use_https": True,
            "verify_ssl": False,
        },
        unique_id="test_gns",
    )


async def test_unload_entry(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test unload entry."""
    mock_gds_entry.add_to_hass(hass)

    hass.data[DOMAIN] = {
        mock_gds_entry.entry_id: {
            "coordinator": MagicMock(),
        }
    }

    result = await async_unload_entry(hass, mock_gds_entry)
    assert result is True


def test_extract_mac_address() -> None:
    """Test Extract mac address."""
    api = MagicMock()
    api.device_mac = "AA:BB:CC:DD:EE:FF"
    assert _extract_mac_address(api) == "AABBCCDDEEFF"


def test_raise_auth_failed() -> None:
    """Test _raise_auth_failed raises ConfigEntryAuthFailed."""
    with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
        _raise_auth_failed()


def test_raise_ha_control_disabled() -> None:
    """Test _raise_ha_control_disabled raises ConfigEntryAuthFailed."""
    with pytest.raises(
        ConfigEntryAuthFailed, match="Home Assistant control is disabled"
    ):
        _raise_ha_control_disabled()


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
async def test_attempt_api_login_re_raises_config_entry_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test _attempt_api_login re-raises ConfigEntryAuthFailed."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}
    api = MagicMock()
    api.login.side_effect = ConfigEntryAuthFailed("Already failed")

    with pytest.raises(ConfigEntryAuthFailed, match="Already failed"):
        await _attempt_api_login(hass, api)


@pytest.mark.asyncio
async def test_attempt_api_login_catches_grandstream_error(hass: HomeAssistant) -> None:
    """Test _attempt_api_login catches GrandstreamHAControlDisabledError from login."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}
    api = MagicMock()
    api.login.side_effect = GrandstreamHAControlDisabledError("HA control disabled")

    with pytest.raises(
        ConfigEntryAuthFailed, match="Home Assistant control is disabled"
    ):
        await _attempt_api_login(hass, api)


@pytest.mark.asyncio
async def test_attempt_api_login_exception(hass: HomeAssistant) -> None:
    """Test Attempt api login exception."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}
    api = MagicMock()
    api.login.side_effect = ValueError("bad")
    await _attempt_api_login(hass, api)


def test_update_device_name() -> None:
    """Test Update device name."""
    device = MagicMock()
    device.name = "Device"
    _update_device_name(device, {"product_name": "GNS"})
    assert device.name == "GNS"


def test_update_firmware_version_from_system_info() -> None:
    """Test Update firmware version from system info."""
    device = MagicMock()
    api = MagicMock()
    _update_firmware_version(device, api, {"product_version": "1.2.3"})
    device.set_firmware_version.assert_called_once_with("1.2.3")


def test_update_firmware_version_from_api() -> None:
    """Test Update firmware version from api."""
    device = MagicMock()
    api = MagicMock()
    api.version = "2.0.0"
    _update_firmware_version(device, api, {"product_version": ""})
    device.set_firmware_version.assert_called_once_with("2.0.0")


def test_update_firmware_version_from_discovery() -> None:
    """Test Update firmware version from discovery fallback."""
    device = MagicMock()
    api = MagicMock()
    api.version = None
    _update_firmware_version(device, api, {}, discovery_version="3.0.0")
    device.set_firmware_version.assert_called_once_with("3.0.0")


@pytest.mark.asyncio
async def test_handle_existing_device_updates(hass: HomeAssistant) -> None:
    """Test Handle existing device updates."""
    device_registry = MagicMock()
    existing_device = MagicMock()
    existing_device.id = "dev"
    existing_device.identifiers = {(DOMAIN, "uid-1")}
    device_registry.devices = {"dev": existing_device}

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        await _handle_existing_device(hass, "uid-1", "Name", "GDS")

    assert device_registry.async_update_device.called is True


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
    test_entry.runtime_data = {}

    mock_api = MagicMock()
    mock_api.host = "192.168.1.100"
    mock_api.device_mac = "AA:BB:CC:DD:EE:FF"

    with patch(
        "homeassistant.components.grandstream_home.DEVICE_CLASS_MAPPING",
        {DEVICE_TYPE_GDS: MagicMock()},
    ):
        device = await _setup_device(hass, test_entry, DEVICE_TYPE_GDS)
        assert device is not None


@pytest.mark.asyncio
async def test_setup_api_catches_grandstream_error(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_api catches GrandstreamHAControlDisabledError from _attempt_api_login."""

    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance"
        ) as mock_create,
        patch(
            "homeassistant.components.grandstream_home._attempt_api_login",
            side_effect=GrandstreamHAControlDisabledError("HA control disabled"),
        ),
    ):
        mock_api = MagicMock()
        mock_create.return_value = mock_api

        with pytest.raises(
            ConfigEntryAuthFailed, match="Home Assistant control is disabled"
        ):
            await _setup_api(hass, mock_gds_entry)


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
async def test_setup_api_with_error_handling_re_raises_auth_failed(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_api_with_error_handling re-raises ConfigEntryAuthFailed."""
    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance"
        ) as mock_create,
        patch(
            "homeassistant.components.grandstream_home._attempt_api_login",
            side_effect=ConfigEntryAuthFailed("Auth failed"),
        ),
    ):
        mock_api = MagicMock()
        mock_create.return_value = mock_api
        hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}

        with pytest.raises(ConfigEntryAuthFailed, match="Auth failed"):
            await _setup_api_with_error_handling(hass, mock_gds_entry, DEVICE_TYPE_GDS)


@pytest.mark.asyncio
async def test_update_stored_data_success(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test _update_stored_data on success."""
    mock_gds_entry.runtime_data = {}

    mock_coordinator = MagicMock()
    mock_device = MagicMock()

    hass.data[DOMAIN] = {mock_gds_entry.entry_id: {"api": MagicMock()}}
    await _update_stored_data(
        hass, mock_gds_entry, mock_coordinator, mock_device, DEVICE_TYPE_GDS
    )

    entry_data = hass.data[DOMAIN][mock_gds_entry.entry_id]
    assert entry_data["coordinator"] == mock_coordinator
    assert entry_data["device"] == mock_device
    assert entry_data["device_type"] == DEVICE_TYPE_GDS


@pytest.mark.asyncio
async def test_update_stored_data_exception(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _update_stored_data handles exceptions."""
    mock_coordinator = MagicMock()
    mock_device = MagicMock()
    mock_dict = MagicMock()
    mock_dict.update.side_effect = ValueError("Update error")
    hass.data[DOMAIN] = {mock_gds_entry.entry_id: mock_dict}

    with pytest.raises(ConfigEntryNotReady, match="Data storage update failed"):
        await _update_stored_data(
            hass, mock_gds_entry, mock_coordinator, mock_device, DEVICE_TYPE_GDS
        )


def test_set_device_network_info_with_api_host(hass: HomeAssistant) -> None:
    """Test _set_device_network_info when API has host."""
    mock_api = MagicMock()
    mock_api.host = "192.168.1.100"
    mock_api.device_mac = "00:0B:82:12:34:56"
    mock_device = MagicMock()
    device_info = {"host": "192.168.1.100", "port": "80", "name": "Test"}

    _set_device_network_info(mock_device, mock_api, device_info)
    mock_device.set_ip_address.assert_called_with("192.168.1.100")
    mock_device.set_mac_address.assert_called_with("00:0B:82:12:34:56")


def test_set_device_network_info_without_api_host(hass: HomeAssistant) -> None:
    """Test _set_device_network_info when API has no host."""
    mock_api = MagicMock()
    delattr(mock_api, "host") if hasattr(mock_api, "host") else None
    mock_device = MagicMock()
    device_info = {"host": "192.168.1.100", "port": "80", "name": "Test"}

    _set_device_network_info(mock_device, mock_api, device_info)
    mock_device.set_ip_address.assert_called_with("192.168.1.100")


@pytest.mark.asyncio
async def test_setup_api_with_error_handling_ha_control_disabled(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_api_with_error_handling handles GrandstreamHAControlDisabledError."""
    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance",
            side_effect=GrandstreamHAControlDisabledError("HA control disabled"),
        ),
        pytest.raises(
            ConfigEntryAuthFailed, match="Home Assistant control is disabled"
        ),
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
            "homeassistant.components.grandstream_home._create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.grandstream_home._update_device_info_from_api",
            return_value=AsyncMock(),
        ),
    ):
        mock_gds_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert result is True
        assert DOMAIN in hass.data
        assert mock_gds_entry.entry_id in hass.data[DOMAIN]
        assert mock_api.login.called


@pytest.mark.enable_socket
async def test_setup_entry_gns_success(hass: HomeAssistant, mock_gns_entry) -> None:
    """Test successful setup of GNS device entry."""
    mock_gns_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "00:0B:82:12:34:57"
    mock_api.host = "192.168.1.101"
    mock_api.get_system_info.return_value = {
        "product_name": "GNS5004E",
        "product_version": "1.0.0",
    }

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.grandstream_home._update_device_info_from_api",
            return_value=AsyncMock(),
        ),
    ):
        mock_gns_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_gns_entry.entry_id)

        assert result is True
        assert DOMAIN in hass.data
        assert mock_gns_entry.entry_id in hass.data[DOMAIN]
        assert mock_api.login.called


@pytest.mark.enable_socket
async def test_setup_entry_login_failure(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test setup continues even when login fails."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = False
    mock_api.device_mac = None
    mock_api.host = "192.168.1.100"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.grandstream_home._update_device_info_from_api",
            return_value=AsyncMock(),
        ),
    ):
        mock_gds_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert result is True
        assert mock_api.login.called


@pytest.mark.enable_socket
async def test_setup_entry_api_exception(hass: HomeAssistant, mock_gds_entry) -> None:
    """Test setup handles API exceptions."""
    with patch(
        "homeassistant.components.grandstream_home._create_api_instance",
        side_effect=Exception("API initialization failed"),
    ):
        mock_gds_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)
        assert result is False


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
            "homeassistant.components.grandstream_home._create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.grandstream_home._update_device_info_from_api",
            return_value=AsyncMock(),
        ),
    ):
        mock_gds_entry.add_to_hass(hass)
        setup_result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)
        assert setup_result is True

        result = await hass.config_entries.async_unload(mock_gds_entry.entry_id)
        assert result is True


@pytest.mark.enable_socket
async def test_setup_entry_coordinator_failure(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test setup handles coordinator initialization failure."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "00:0B:82:12:34:56"
    mock_api.host = "192.168.1.100"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=Exception("Coordinator refresh failed")
    )

    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
    ):
        mock_gds_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_gds_entry.entry_id)
        assert result is False


@pytest.mark.enable_socket
async def test_setup_entry_stores_correct_data(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test that setup stores correct data in hass.data."""
    mock_gds_entry.add_to_hass(hass)

    mock_api = MagicMock()
    mock_api.login.return_value = True
    mock_api.device_mac = "00:0B:82:12:34:56"
    mock_api.host = "192.168.1.100"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.grandstream_home.GrandstreamCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.grandstream_home._update_device_info_from_api",
            return_value=AsyncMock(),
        ),
    ):
        mock_gds_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_gds_entry.entry_id)

        assert DOMAIN in hass.data
        assert mock_gds_entry.entry_id in hass.data[DOMAIN]

        entry_data = hass.data[DOMAIN][mock_gds_entry.entry_id]
        assert "api" in entry_data
        assert "coordinator" in entry_data
        assert "device" in entry_data
        assert "device_type" in entry_data
        assert entry_data["device_type"] == DEVICE_TYPE_GDS


def test_create_api_instance_unknown_device_type() -> None:
    """Test _create_api_instance with unknown device type falls back to default."""
    mock_api_class = MagicMock()

    entry = MagicMock()
    entry.data = {
        "host": "192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",  # Use plaintext for simplicity
        "use_https": True,
        "verify_ssl": False,
    }
    entry.unique_id = "test_id"

    # decrypt_password will return the password as-is for short strings
    result = _create_api_instance(mock_api_class, "UNKNOWN_TYPE", entry)

    # The password should be decrypted (for short strings, returns as-is)
    mock_api_class.assert_called_once()
    assert result == mock_api_class.return_value


@pytest.mark.asyncio
async def test_setup_api_with_error_handling_import_error(
    hass: HomeAssistant, mock_gds_entry
) -> None:
    """Test _setup_api_with_error_handling handles ImportError."""
    hass.data[DOMAIN] = {"api_lock": asyncio.Lock()}

    with (
        patch(
            "homeassistant.components.grandstream_home._create_api_instance",
            side_effect=ImportError("Import error"),
        ),
        pytest.raises(ConfigEntryNotReady, match="API setup failed"),
    ):
        await _setup_api_with_error_handling(hass, mock_gds_entry, DEVICE_TYPE_GDS)


@pytest.mark.asyncio
async def test_update_device_info_from_api_gns(hass: HomeAssistant) -> None:
    """Test _update_device_info_from_api for GNS device."""

    mock_api = MagicMock()
    mock_api.get_system_info.return_value = {
        "product_name": "GNS5004E",
        "product_version": "1.0.0",
    }

    mock_device = MagicMock()
    mock_device.name = "Test GNS"

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with patch.object(
        hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
    ):
        await _update_device_info_from_api(
            hass, mock_api, DEVICE_TYPE_GNS_NAS, mock_device, None
        )

    mock_device.set_firmware_version.assert_called_with("1.0.0")


@pytest.mark.asyncio
async def test_update_device_info_from_api_gns_no_system_info(
    hass: HomeAssistant,
) -> None:
    """Test _update_device_info_from_api for GNS device when system_info is None."""

    mock_api = MagicMock()
    mock_api.get_system_info.return_value = None

    mock_device = MagicMock()

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with patch.object(
        hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
    ):
        await _update_device_info_from_api(
            hass, mock_api, DEVICE_TYPE_GNS_NAS, mock_device, None
        )


@pytest.mark.asyncio
async def test_update_device_info_from_api_gns_exception(hass: HomeAssistant) -> None:
    """Test _update_device_info_from_api for GNS device with exception."""

    mock_api = MagicMock()
    mock_api.get_system_info.side_effect = OSError("Connection error")

    mock_device = MagicMock()

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs) if args or kwargs else func()

    with patch.object(
        hass, "async_add_executor_job", side_effect=mock_async_add_executor_job
    ):
        # Should not raise, just log warning
        await _update_device_info_from_api(
            hass, mock_api, DEVICE_TYPE_GNS_NAS, mock_device, None
        )


@pytest.mark.asyncio
async def test_update_device_info_from_api_gds_with_discovery_version(
    hass: HomeAssistant,
) -> None:
    """Test _update_device_info_from_api for GDS device with discovery version."""

    mock_api = MagicMock()
    mock_device = MagicMock()

    await _update_device_info_from_api(
        hass, mock_api, DEVICE_TYPE_GDS, mock_device, "1.2.3"
    )

    mock_device.set_firmware_version.assert_called_with("1.2.3")


def test_update_device_name_already_has_model(hass: HomeAssistant) -> None:
    """Test _update_device_name when name already has model info."""
    mock_device = MagicMock()
    mock_device.name = "GNS5004E Device"  # Already contains GNS

    _update_device_name(mock_device, {"product_name": "GNS5004E"})

    # Name should not be updated since it already has model info
    assert mock_device.name == "GNS5004E Device"


def test_update_device_name_empty_product_name(hass: HomeAssistant) -> None:
    """Test _update_device_name with empty product name."""
    mock_device = MagicMock()
    mock_device.name = "Test Device"

    _update_device_name(mock_device, {"product_name": ""})

    # Name should not be updated with empty product name
    assert mock_device.name == "Test Device"
