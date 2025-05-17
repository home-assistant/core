"""Test Suez_water sensor platform."""

from datetime import date
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.suez_water.const import DATA_REFRESH_INTERVAL
from homeassistant.components.suez_water.coordinator import PySuezError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors_valid_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that suez_water sensor is loaded and in a valid state."""
    with patch("homeassistant.components.suez_water.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    state = hass.states.get("sensor.suez_mock_device_water_usage_yesterday")
    assert state
    previous: dict = state.attributes["previous_month_consumption"]
    assert previous
    assert previous.get(date.fromisoformat("2024-12-01")) is None
    assert previous.get(str(date.fromisoformat("2024-12-01"))) == 154


@pytest.mark.parametrize("method", [("fetch_aggregated_data"), ("get_price")])
async def test_sensors_failed_update(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    method: str,
) -> None:
    """Test that suez_water sensor reflect failure when api fails."""
    with patch("homeassistant.components.suez_water.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform_with_given_assertion(
        hass, entity_registry, snapshot, "valid", mock_config_entry.entry_id
    )

    getattr(suez_client, method).side_effect = PySuezError("Should fail to update")

    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    await snapshot_platform_with_given_assertion(
        hass, entity_registry, snapshot, "error", mock_config_entry.entry_id
    )


async def snapshot_platform_with_given_assertion(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    snapshot_assertion_suffix_name: str,
    config_entry_id: str,
) -> None:
    """Snapshot a platform."""
    entity_entries = er.async_entries_for_config_entry(entity_registry, config_entry_id)
    assert entity_entries
    assert len({entity_entry.domain for entity_entry in entity_entries}) == 1, (
        "Please limit the loaded platforms to 1 platform."
    )
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(
            name=f"{entity_entry.entity_id}_{snapshot_assertion_suffix_name}-entry"
        )
        assert entity_entry.disabled_by is None, "Please enable all entities."
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state == snapshot(
            name=f"{entity_entry.entity_id}_{snapshot_assertion_suffix_name}-state"
        )
