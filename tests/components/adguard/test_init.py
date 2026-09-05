"""Tests for the AdGuard Home."""

from unittest.mock import AsyncMock, patch

from adguardhome import AdGuardHomeConnectionError
import pytest

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.mark.usefixtures("init_integration")
async def test_setup(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup."""
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup failed."""
    mock_adguard.version.side_effect = AdGuardHomeConnectionError("Connection error")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the device is identified by a two part identifier."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.adguard.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.identifiers == {(DOMAIN, mock_config_entry.entry_id)}


async def test_device_identifiers_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the device created by an older version is migrated."""
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "127.0.0.1", 3000, "/control")},  # type: ignore[arg-type]
        name="AdGuard Home",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated = device_registry.async_get(device.id)
    assert migrated is not None
    assert migrated.identifiers == {(DOMAIN, mock_config_entry.entry_id)}


async def test_device_identifiers_migration_when_unavailable(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the device is migrated even when the instance cannot be reached."""
    mock_adguard.version.side_effect = AdGuardHomeConnectionError("Connection error")

    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "127.0.0.1", 3000, "/control")},  # type: ignore[arg-type]
        name="AdGuard Home",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    migrated = device_registry.async_get(device.id)
    assert migrated is not None
    assert migrated.identifiers == {(DOMAIN, mock_config_entry.entry_id)}


async def test_device_identifiers_migration_with_duplicate(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device left behind by a downgrade is cleaned up."""
    mock_config_entry.add_to_hass(hass)
    current = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name="AdGuard Home",
    )
    duplicate = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "127.0.0.1", 3000, "/control")},  # type: ignore[arg-type]
        name="AdGuard Home",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert device_registry.async_get(duplicate.id) is None
    assert device_registry.async_get(current.id) is not None
