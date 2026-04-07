"""Tests for the Mitsubishi Comfort integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import DeviceInfo

from homeassistant.components.mitsubishi_comfort import (
    CONF_DEVICES,
    _devices_to_cache,
    _make_device,
    _merge_cached_into_devices,
    _retry_incomplete_devices,
)
from homeassistant.components.mitsubishi_comfort.const import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_RESPONSE_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "SERIAL001" in mock_config_entry.runtime_data


async def test_setup_entry_persists_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test setup persists discovered credentials in entry.data."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert CONF_DEVICES in mock_config_entry.data
    assert "SERIAL001" in mock_config_entry.data[CONF_DEVICES]


async def test_setup_entry_login_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when login fails."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=False)
    mock_account.close = AsyncMock()

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when no devices are discovered."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(return_value={})
    mock_account.close = AsyncMock()

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_incomplete_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test setup fails when all devices have incomplete credentials."""
    mock_config_entry.add_to_hass(hass)
    mock_device_info.password = ""
    mock_device_info.address = ""

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )
    mock_account.get_passwords_via_websocket = AsyncMock(return_value={})
    mock_account.close = AsyncMock()

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_with_cached_credentials(
    hass: HomeAssistant,
    mock_device_info: DeviceInfo,
    mock_indoor_unit: MagicMock,
) -> None:
    """Test setup merges cached credentials into discovered devices."""
    cached: dict[str, dict[str, Any]] = {
        "SERIAL001": {
            "address": "192.168.1.100",
            "password": "dGVzdHBhc3M=",
            "crypto_serial": "0102030405060708090a",
        }
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": MOCK_USERNAME,
            "password": MOCK_PASSWORD,
            CONF_DEVICES: cached,
        },
        unique_id=MOCK_USERNAME,
    )
    entry.add_to_hass(hass)

    # Device discovered without password
    mock_device_info.password = ""

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )
    mock_account.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.IndoorUnit",
            return_value=mock_indoor_unit,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.KumoStation",
            return_value=mock_indoor_unit,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert mock_device_info.password == "dGVzdHBhc3M="


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test unloading a config entry."""
    _, mock_device = mock_setup_integration
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_device.close.assert_awaited_once()


async def test_make_device_indoor_unit(
    mock_device_info: DeviceInfo,
) -> None:
    """Test _make_device creates an IndoorUnit for indoor devices."""
    assert mock_device_info.is_indoor_unit is True

    with patch("homeassistant.components.mitsubishi_comfort.IndoorUnit") as mock_cls:
        _make_device(mock_device_info, "SERIAL001")
        mock_cls.assert_called_once_with(
            name=mock_device_info.label,
            address=mock_device_info.address,
            password_b64=mock_device_info.password,
            crypto_serial_hex=mock_device_info.crypto_serial,
            serial="SERIAL001",
            connect_timeout=DEFAULT_CONNECT_TIMEOUT,
            response_timeout=DEFAULT_RESPONSE_TIMEOUT,
        )


async def test_make_device_kumo_station() -> None:
    """Test _make_device creates a KumoStation for non-indoor devices."""
    headless_info = DeviceInfo(
        serial="SERIAL002",
        label="Kumo Station",
        address="192.168.1.200",
        mac="11:22:33:44:55:66",
        unit_type="headless",
        password="cHdk",
        crypto_serial="aabbccdd",
    )
    assert headless_info.is_indoor_unit is False

    with patch("homeassistant.components.mitsubishi_comfort.KumoStation") as mock_cls:
        _make_device(headless_info, "SERIAL002")
        mock_cls.assert_called_once_with(
            name="Kumo Station",
            address="192.168.1.200",
            password_b64="cHdk",
            crypto_serial_hex="aabbccdd",
            serial="SERIAL002",
            connect_timeout=DEFAULT_CONNECT_TIMEOUT,
            response_timeout=DEFAULT_RESPONSE_TIMEOUT,
        )


async def test_devices_to_cache(
    mock_device_info: DeviceInfo,
) -> None:
    """Test _devices_to_cache serializes device credentials."""
    result = _devices_to_cache({"SERIAL001": mock_device_info})

    assert "SERIAL001" in result
    assert result["SERIAL001"]["address"] == mock_device_info.address
    assert result["SERIAL001"]["password"] == mock_device_info.password
    assert result["SERIAL001"]["label"] == mock_device_info.label


async def test_merge_cached_into_devices(
    mock_device_info: DeviceInfo,
) -> None:
    """Test _merge_cached_into_devices merges missing fields."""
    mock_device_info.address = ""
    mock_device_info.password = ""
    mock_device_info.crypto_serial = ""

    cached: dict[str, dict[str, Any]] = {
        "SERIAL001": {
            "address": "192.168.1.100",
            "password": "cached_pw",
            "crypto_serial": "cached_cs",
        }
    }

    updated = _merge_cached_into_devices({"SERIAL001": mock_device_info}, cached)

    assert "SERIAL001" in updated
    assert mock_device_info.address == "192.168.1.100"
    assert mock_device_info.password == "cached_pw"
    assert mock_device_info.crypto_serial == "cached_cs"


async def test_merge_cached_skips_existing_values(
    mock_device_info: DeviceInfo,
) -> None:
    """Test _merge_cached_into_devices doesn't overwrite existing values."""
    original_addr = mock_device_info.address
    original_pw = mock_device_info.password
    original_cs = mock_device_info.crypto_serial

    cached: dict[str, dict[str, Any]] = {
        "SERIAL001": {
            "address": "10.0.0.1",
            "password": "other_pw",
            "crypto_serial": "other_cs",
        }
    }

    updated = _merge_cached_into_devices({"SERIAL001": mock_device_info}, cached)

    assert updated == []
    assert mock_device_info.address == original_addr
    assert mock_device_info.password == original_pw
    assert mock_device_info.crypto_serial == original_cs


async def test_merge_cached_ignores_unknown_serials(
    mock_device_info: DeviceInfo,
) -> None:
    """Test _merge_cached_into_devices ignores serials not in devices."""
    cached: dict[str, dict[str, Any]] = {
        "UNKNOWN_SERIAL": {
            "address": "10.0.0.1",
            "password": "pw",
        }
    }

    updated = _merge_cached_into_devices({"SERIAL001": mock_device_info}, cached)
    assert updated == []


async def test_setup_entry_mixed_complete_incomplete(
    hass: HomeAssistant,
    mock_indoor_unit: MagicMock,
) -> None:
    """Test setup with one complete and one incomplete device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": MOCK_USERNAME,
            "password": MOCK_PASSWORD,
        },
        unique_id=MOCK_USERNAME,
    )
    entry.add_to_hass(hass)

    complete_info = DeviceInfo(
        serial="SERIAL001",
        label="Living Room",
        address="192.168.1.100",
        mac="AA:BB:CC:DD:EE:FF",
        unit_type="ductless",
        password="dGVzdHBhc3M=",
        crypto_serial="0102030405060708090a",
    )
    incomplete_info = DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="",
        crypto_serial="",
    )

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={
            "SERIAL001": complete_info,
            "SERIAL002": incomplete_info,
        }
    )
    mock_account.get_passwords_via_websocket = AsyncMock(return_value={})
    mock_account.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.IndoorUnit",
            return_value=mock_indoor_unit,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.KumoStation",
            return_value=mock_indoor_unit,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort._retry_incomplete_devices",
        ) as mock_retry,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "SERIAL001" in entry.runtime_data
    assert "SERIAL002" not in entry.runtime_data
    mock_retry.assert_called_once()


async def test_retry_incomplete_devices_success(
    hass: HomeAssistant,
    mock_indoor_unit: MagicMock,
) -> None:
    """Test _retry_incomplete_devices succeeds when passwords are returned."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": MOCK_USERNAME, "password": MOCK_PASSWORD},
        unique_id=MOCK_USERNAME,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = {"SERIAL001": MagicMock()}

    incomplete_info = DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="192.168.1.200",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="",
        crypto_serial="abcdef1234",
    )

    mock_account = AsyncMock()
    mock_account.get_passwords_via_websocket = AsyncMock(
        return_value={"SERIAL002": "bmV3cGFzcw=="}
    )
    mock_account.close = AsyncMock()

    devices = {"SERIAL002": incomplete_info}
    incomplete_serials = ["SERIAL002"]

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "homeassistant.components.mitsubishi_comfort.IndoorUnit",
            return_value=mock_indoor_unit,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.KumoStation",
            return_value=mock_indoor_unit,
        ),
        patch.object(
            hass.config_entries,
            "async_reload",
            new_callable=AsyncMock,
        ) as mock_reload,
    ):
        await _retry_incomplete_devices(
            hass, entry, mock_account, devices, incomplete_serials
        )

    assert incomplete_info.password == "bmV3cGFzcw=="
    mock_reload.assert_awaited_once_with(entry.entry_id)
    mock_account.close.assert_awaited_once()


async def test_retry_incomplete_devices_no_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Test _retry_incomplete_devices exits early if entry has no runtime_data."""
    entry = MagicMock()
    del entry.runtime_data

    mock_account = AsyncMock()
    mock_account.close = AsyncMock()
    devices: dict[str, DeviceInfo] = {}
    incomplete_serials = ["SERIAL002"]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await _retry_incomplete_devices(
            hass, entry, mock_account, devices, incomplete_serials
        )

    mock_account.get_passwords_via_websocket.assert_not_awaited()
    mock_account.close.assert_awaited_once()


async def test_retry_incomplete_devices_all_attempts_fail(
    hass: HomeAssistant,
) -> None:
    """Test _retry_incomplete_devices logs warning after all retries fail."""
    entry = MagicMock()
    entry.runtime_data = {}

    incomplete_info = DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="192.168.1.200",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="",
        crypto_serial="abcdef1234",
    )

    mock_account = AsyncMock()
    mock_account.get_passwords_via_websocket = AsyncMock(return_value={})
    mock_account.close = AsyncMock()

    devices = {"SERIAL002": incomplete_info}
    incomplete_serials = ["SERIAL002"]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await _retry_incomplete_devices(
            hass, entry, mock_account, devices, incomplete_serials
        )

    assert incomplete_info.password == ""
    assert "SERIAL002" in incomplete_serials
    mock_account.close.assert_awaited_once()
