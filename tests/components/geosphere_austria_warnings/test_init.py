"""Tests for the GeoSphere Austria Warnings integration setup."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pygeosphere_warnings import (
    GeoSphereApiError,
    GeoSphereConnectionError,
    GeoSphereMunicipalityNotFoundError,
)
import pytest

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.coordinator import (
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_client")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        pytest.param(
            GeoSphereConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
        pytest.param(GeoSphereApiError, ConfigEntryState.SETUP_RETRY, id="api_error"),
        pytest.param(
            GeoSphereMunicipalityNotFoundError,
            ConfigEntryState.SETUP_ERROR,
            id="municipality_not_found",
        ),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test the entry state when the first refresh fails."""
    mock_client.get_last_modified.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_warnings_fetch_skipped_when_unchanged(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the HEAD precheck avoids refetching unchanged warnings."""
    await setup_integration(hass, mock_config_entry)
    assert mock_client.get_warnings_for_coords.call_count == 1

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.get_warnings_for_coords.call_count == 1

    # New Last-Modified: warnings are refetched
    mock_client.get_last_modified.return_value = datetime(
        2023, 3, 27, 12, 0, tzinfo=UTC
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_client.get_warnings_for_coords.call_count == 2


@pytest.mark.parametrize(
    "custom_entity_id",
    [None, "sensor.my_custom_warning"],
    ids=["default_entity_id", "custom_entity_id"],
)
@pytest.mark.usefixtures("mock_client")
async def test_migrate_warning_level_preserves_registry_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    custom_entity_id: str | None,
) -> None:
    """Migrate the legacy sensor while preserving its registry and entity IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        data=mock_config_entry.data,
        unique_id="30740",
        version=1,
    )
    entry.add_to_hass(hass)

    old = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="30740-warning_level",
        config_entry=entry,
        suggested_object_id="schwechat_warning_level",
    )
    if custom_entity_id is not None:
        old = entity_registry.async_update_entity(
            old.entity_id,
            new_entity_id=custom_entity_id,
        )

    old_id = old.id
    old_entity_id = old.entity_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2

    migrated = entity_registry.async_get(old_entity_id)
    assert migrated is not None
    assert migrated.id == old_id
    assert migrated.entity_id == old_entity_id
    assert migrated.unique_id == "30740-active_warning_level"
    assert hass.states.get(old_entity_id) is not None


async def test_migration_conflict(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not migrate or advance the version when the target ID conflicts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        data=mock_config_entry.data,
        unique_id="30740",
        version=1,
    )
    entry.add_to_hass(hass)

    old = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="30740-warning_level",
        config_entry=entry,
    )

    target = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="30740-active_warning_level",
        config_entry=entry,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    mock_setup_entry.assert_not_called()

    target_after = entity_registry.async_get(target.entity_id)
    assert target_after is not None
    assert target_after.id == target.id
    assert target_after.unique_id == "30740-active_warning_level"

    old_after = entity_registry.async_get(old.entity_id)
    assert old_after is not None
    assert old_after.id == old.id
    assert old_after.unique_id == "30740-warning_level"
