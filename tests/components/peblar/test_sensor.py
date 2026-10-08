"""Tests for the Peblar sensor platform."""

from enum import StrEnum

from peblar import ChargeLimiter, CPState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import (
    DOMAIN,
    PEBLAR_CHARGE_LIMITER_TO_HOME_ASSISTANT,
    PEBLAR_CP_STATE_TO_HOME_ASSISTANT,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2024-12-21 21:45:00")
@pytest.mark.parametrize("init_integration", [Platform.SENSOR], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure all entities are correctly assigned to the Peblar EV charger
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "23-45-A4O-MOF"), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("mapping", "states"),
    [
        (PEBLAR_CHARGE_LIMITER_TO_HOME_ASSISTANT, ChargeLimiter),
        (PEBLAR_CP_STATE_TO_HOME_ASSISTANT, CPState),
    ],
    ids=["charge_limiter", "cp_state"],
)
def test_all_library_states_are_mapped(
    mapping: dict[StrEnum, str | None], states: type[StrEnum]
) -> None:
    """Test every Peblar library state has a mapping."""
    assert set(mapping) == set(states)
