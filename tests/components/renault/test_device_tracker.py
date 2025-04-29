"""Tests for Renault sensors."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import check_entities_unavailable
from .const import MOCK_VEHICLES

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.DEVICE_TRACKER]):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
async def test_device_trackers(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault device trackers."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.usefixtures("fixtures_with_no_data")
async def test_device_tracker_empty(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for Renault device trackers with empty data from Renault."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entities are correctly registered
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == snapshot

    # Ensure entity states are correct
    states = [hass.states.get(ent.entity_id) for ent in entity_entries]
    assert states == snapshot


@pytest.mark.usefixtures("fixtures_with_invalid_upstream_exception")
async def test_device_tracker_errors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    vehicle_type: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault device trackers with temporary failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]

    expected_entities = mock_vehicle[Platform.DEVICE_TRACKER]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities_unavailable(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("fixtures_with_access_denied_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_device_tracker_access_denied(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault device trackers with access denied failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_device_tracker_not_supported(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for Renault device trackers with not supported failure."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 0
