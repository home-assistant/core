"""Tests for the Mitsubishi Comfort integration setup."""

from unittest.mock import AsyncMock, MagicMock

from mitsubishi_comfort import DeviceInfo
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import pytest

from homeassistant.components.mitsubishi_comfort.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL001")


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (AuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (DeviceConnectionError("Connection refused"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_login_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup translates login failures into the expected config entry state."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_account.login.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_setup_entry_no_devices_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Test setup raises a setup error when no devices are found."""
    mock_config_entry.add_to_hass(hass)
    mock_cloud_account.discover_devices.return_value = {}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_incomplete_credentials_loads_empty(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_cloud_account: AsyncMock,
) -> None:
    """Test setup loads with no entities when devices have incomplete credentials."""
    mock_config_entry.add_to_hass(hass)
    mock_device_info.password = ""
    mock_device_info.address = ""

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_setup_entry_skips_incomplete_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_device_info: DeviceInfo,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> None:
    """Test setup skips incomplete devices and creates complete ones."""
    incomplete_info = DeviceInfo(
        serial="SERIAL002",
        label="Bedroom",
        address="",
        mac="11:22:33:44:55:66",
        unit_type="ductless",
        password="",
        crypto_serial="",
    )
    mock_account, _ = mock_setup_integration
    mock_account.discover_devices.return_value = {
        "SERIAL001": mock_device_info,
        "SERIAL002": incomplete_info,
    }
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL001")
    assert entity_registry.async_get_entity_id("climate", DOMAIN, "SERIAL002") is None


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
