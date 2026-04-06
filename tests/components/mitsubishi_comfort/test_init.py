"""Tests for the Mitsubishi Comfort integration setup."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import DeviceInfo
import pytest

from homeassistant.components.mitsubishi_comfort import (
    _load_cached_credentials,
    _make_device,
    _merge_cached_into_devices,
    _parse_kumo_cache,
    _save_credentials,
)
from homeassistant.components.mitsubishi_comfort.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry  # noqa: TID251


@pytest.fixture(autouse=True)
def mock_platform_setup() -> Generator[AsyncMock]:
    """Prevent actual platform setup during init tests."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=None,
    ) as mock:
        yield mock


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value={},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.save_json",
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiComfortCoordinator",
        ) as mock_coordinator_cls,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.close = AsyncMock()
        mock_coordinator_cls.return_value = mock_coordinator

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == {"SERIAL001": mock_coordinator}


async def test_setup_entry_login_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when login fails."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=False)

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

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value={},
        ),
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
    # Remove the password to make credentials incomplete
    mock_device_info.password = ""
    mock_device_info.address = ""

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value={},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.save_json",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_with_cached_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test setup merges cached credentials into discovered devices."""
    mock_config_entry.add_to_hass(hass)

    # Device discovered without password
    mock_device_info.password = ""
    cached: dict[str, dict[str, Any]] = {
        "SERIAL001": {
            "address": "192.168.1.100",
            "password": "dGVzdHBhc3M=",
            "crypto_serial": "0102030405060708090a",
        }
    }

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value=cached,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.save_json",
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiComfortCoordinator",
        ) as mock_coordinator_cls,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.close = AsyncMock()
        mock_coordinator_cls.return_value = mock_coordinator

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Password should have been restored from cache
    assert mock_device_info.password == "dGVzdHBhc3M="


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value={},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.save_json",
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiComfortCoordinator",
        ) as mock_coordinator_cls,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.close = AsyncMock()
        mock_coordinator_cls.return_value = mock_coordinator

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_coordinator.device.close.assert_awaited_once()


async def test_setup_entry_with_dhcp_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test setup with DHCP-discovered IPs for devices missing addresses."""
    mock_config_entry.add_to_hass(hass)

    # Device without address
    mock_device_info.address = ""
    hass.data[f"{DOMAIN}_dhcp_discovered"] = {"AA:BB:CC:DD:EE:FF": "192.168.1.200"}

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=True)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )

    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.load_json",
            return_value={},
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.save_json",
        ),
        patch(
            "homeassistant.components.mitsubishi_comfort.probe_candidate_ips",
            return_value={"SERIAL001": "192.168.1.200"},
        ) as mock_probe,
        patch(
            "homeassistant.components.mitsubishi_comfort.MitsubishiComfortCoordinator",
        ) as mock_coordinator_cls,
    ):
        mock_coordinator = MagicMock()
        mock_coordinator.device = MagicMock()
        mock_coordinator.device.close = AsyncMock()
        mock_coordinator_cls.return_value = mock_coordinator

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_probe.assert_awaited_once()
    assert mock_device_info.address == "192.168.1.200"


async def test_load_cached_credentials_returns_cached(
    hass: HomeAssistant,
) -> None:
    """Test _load_cached_credentials returns cached data."""
    cached = {"SERIAL001": {"address": "192.168.1.100", "password": "pw"}}
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=cached,
    ):
        result = _load_cached_credentials(hass)

    assert result == cached


async def test_load_cached_credentials_falls_back_to_kumo_cache(
    hass: HomeAssistant,
) -> None:
    """Test _load_cached_credentials falls back to legacy kumo_cache.json."""
    kumo_data = [
        {},
        {},
        {
            "children": [
                {
                    "zoneTable": {
                        "SERIAL001": {"address": "192.168.1.100"},
                    }
                }
            ]
        },
    ]

    def mock_load(path: str) -> dict | list:
        if "kumo_cache" in path:
            return kumo_data
        return {}

    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        side_effect=mock_load,
    ):
        result = _load_cached_credentials(hass)

    assert result == {"SERIAL001": {"address": "192.168.1.100"}}


async def test_load_cached_credentials_empty_on_error(
    hass: HomeAssistant,
) -> None:
    """Test _load_cached_credentials returns empty on errors."""
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        side_effect=OSError("File not found"),
    ):
        result = _load_cached_credentials(hass)

    assert result == {}


async def test_parse_kumo_cache_with_grandchildren(
    hass: HomeAssistant,
) -> None:
    """Test _parse_kumo_cache handles nested grandchildren."""
    kumo_data = [
        {},
        {},
        {
            "children": [
                {
                    "zoneTable": {},
                    "children": [
                        {
                            "zoneTable": {
                                "SERIAL002": {"address": "192.168.1.200"},
                            }
                        }
                    ],
                }
            ]
        },
    ]

    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=kumo_data,
    ):
        result = _parse_kumo_cache(hass)

    assert result == {"SERIAL002": "192.168.1.200"}


async def test_parse_kumo_cache_skips_invalid_addresses(
    hass: HomeAssistant,
) -> None:
    """Test _parse_kumo_cache skips N/A and empty addresses."""
    kumo_data = [
        {},
        {},
        {
            "children": [
                {
                    "zoneTable": {
                        "S1": {"address": "N/A"},
                        "S2": {"address": "empty"},
                        "S3": {"address": ""},
                        "S4": {"address": "192.168.1.1"},
                    }
                }
            ]
        },
    ]

    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=kumo_data,
    ):
        result = _parse_kumo_cache(hass)

    assert result == {"S4": "192.168.1.1"}


async def test_parse_kumo_cache_malformed_data(
    hass: HomeAssistant,
) -> None:
    """Test _parse_kumo_cache handles various malformed inputs."""
    # Not a list
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value={"not": "a list"},
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}

    # List too short
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=[{}, {}],
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}

    # Entry not a dict
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=[{}, {}, "not a dict"],
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}

    # Children not a list
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=[{}, {}, {"children": "not a list"}],
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}

    # Child not a dict
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=[{}, {}, {"children": ["not a dict"]}],
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}

    # Grandchildren not a list
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=[
            {},
            {},
            {"children": [{"zoneTable": {}, "children": "not a list"}]},
        ],
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}

    # Grandchild not a dict
    with patch(
        "homeassistant.components.mitsubishi_comfort.load_json",
        return_value=[
            {},
            {},
            {"children": [{"zoneTable": {}, "children": ["not a dict"]}]},
        ],
    ):
        result = _parse_kumo_cache(hass)
    assert result == {}


async def test_make_device_indoor_unit(
    mock_device_info: DeviceInfo,
) -> None:
    """Test _make_device creates an IndoorUnit for indoor devices."""
    # DeviceInfo with unit_type="ductless" has is_indoor_unit=True
    assert mock_device_info.is_indoor_unit is True

    with patch("homeassistant.components.mitsubishi_comfort.IndoorUnit") as mock_cls:
        _make_device(mock_device_info, "SERIAL001", 1.2, 8.0)
        mock_cls.assert_called_once_with(
            name=mock_device_info.label,
            address=mock_device_info.address,
            password_b64=mock_device_info.password,
            crypto_serial_hex=mock_device_info.crypto_serial,
            serial="SERIAL001",
            connect_timeout=1.2,
            response_timeout=8.0,
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
        _make_device(headless_info, "SERIAL002", 1.2, 8.0)
        mock_cls.assert_called_once_with(
            name="Kumo Station",
            address="192.168.1.200",
            password_b64="cHdk",
            crypto_serial_hex="aabbccdd",
            serial="SERIAL002",
            connect_timeout=1.2,
            response_timeout=8.0,
        )


async def test_save_credentials(
    hass: HomeAssistant,
    mock_device_info: DeviceInfo,
) -> None:
    """Test _save_credentials saves device data to JSON."""
    with patch("homeassistant.components.mitsubishi_comfort.save_json") as mock_save:
        _save_credentials(hass, {"SERIAL001": mock_device_info})

    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][1]
    assert "SERIAL001" in saved_data
    assert saved_data["SERIAL001"]["address"] == mock_device_info.address


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

    # Nothing should be updated since device already has values
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
