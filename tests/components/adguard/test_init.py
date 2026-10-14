"""Tests for the AdGuard Home."""

from unittest.mock import AsyncMock, patch

from adguardhome import (
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeResponseError,
)
import pytest

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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


@pytest.mark.parametrize(
    "error",
    [
        AdGuardHomeConnectionError("Connection error"),
        AdGuardHomeResponseError("Server error", status=500, body=""),
    ],
)
async def test_setup_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test the adguard setup is retried when AdGuard Home fails."""
    mock_adguard.status.side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_authentication_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejected credentials ask for new ones."""
    mock_adguard.status.side_effect = AdGuardHomeAuthenticationError("Nope")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


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
    mock_adguard.status.side_effect = AdGuardHomeConnectionError("Connection error")

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


@pytest.mark.parametrize(
    ("platform", "legacy_unique_id", "unique_id"),
    [
        (
            Platform.SENSOR,
            "adguard_127.0.0.1_3000_sensor_dns_queries",
            "01JADGUARDHOME0000000000000_dns_queries",
        ),
        (
            Platform.SWITCH,
            "adguard_127.0.0.1_3000_switch_safebrowsing",
            "01JADGUARDHOME0000000000000_safebrowsing",
        ),
        (
            Platform.UPDATE,
            "adguard_127.0.0.1_3000_update",
            "01JADGUARDHOME0000000000000",
        ),
    ],
)
async def test_unique_id_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    platform: Platform,
    legacy_unique_id: str,
    unique_id: str,
) -> None:
    """Test entities identified by host and port move to the entry ID."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, minor_version=1)
    entity = entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        legacy_unique_id,
        config_entry=mock_config_entry,
    )
    other = entity_registry.async_get_or_create(
        platform,
        DOMAIN,
        "adguard_192.168.1.2_3000_sensor_dns_queries",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.minor_version == 2

    migrated = entity_registry.async_get(entity.entity_id)
    assert migrated
    assert migrated.unique_id == unique_id

    # Entities of another host are not this entry's to migrate.
    untouched = entity_registry.async_get(other.entity_id)
    assert untouched
    assert untouched.unique_id == "adguard_192.168.1.2_3000_sensor_dns_queries"


async def test_unique_id_migration_already_in_use(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entity is left alone when its new unique ID is taken."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, minor_version=1)
    current = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "01JADGUARDHOME0000000000000_dns_queries",
        config_entry=mock_config_entry,
    )
    legacy = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "adguard_127.0.0.1_3000_sensor_dns_queries",
        config_entry=mock_config_entry,
    )

    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.minor_version == 2

    entity = entity_registry.async_get(current.entity_id)
    assert entity
    assert entity.unique_id == "01JADGUARDHOME0000000000000_dns_queries"

    entity = entity_registry.async_get(legacy.entity_id)
    assert entity
    assert entity.unique_id == "adguard_127.0.0.1_3000_sensor_dns_queries"
