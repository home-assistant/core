"""Tests for the Mitsubishi Comfort integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import DeviceInfo
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError

from homeassistant.components.mitsubishi_comfort.const import DOMAIN
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


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup returns a setup error when credentials are rejected."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(side_effect=AuthenticationError("bad creds"))

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the cloud is unreachable."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(
        side_effect=DeviceConnectionError("Connection refused")
    )

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_devices_loads_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds with an empty runtime_data when no devices are found."""
    mock_config_entry.add_to_hass(hass)

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=None)
    mock_account.discover_devices = AsyncMock(return_value={})

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == {}


async def test_setup_entry_incomplete_credentials_loads_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test setup loads with no coordinators when devices have incomplete credentials."""
    mock_config_entry.add_to_hass(hass)
    mock_device_info.password = ""
    mock_device_info.address = ""

    mock_account = AsyncMock()
    mock_account.login = AsyncMock(return_value=None)
    mock_account.discover_devices = AsyncMock(
        return_value={"SERIAL001": mock_device_info}
    )

    with patch(
        "homeassistant.components.mitsubishi_comfort.MitsubishiCloudAccount",
        return_value=mock_account,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == {}


async def test_setup_entry_skips_incomplete_devices(
    hass: HomeAssistant,
    mock_indoor_unit: MagicMock,
) -> None:
    """Test setup skips incomplete devices and only creates coordinators for complete ones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": MOCK_USERNAME,
            "password": MOCK_PASSWORD,
        },
        unique_id="user-12345",
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
    mock_account.login = AsyncMock(return_value=None)
    mock_account.discover_devices = AsyncMock(
        return_value={
            "SERIAL001": complete_info,
            "SERIAL002": incomplete_info,
        }
    )

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
    assert "SERIAL001" in entry.runtime_data
    assert "SERIAL002" not in entry.runtime_data


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
