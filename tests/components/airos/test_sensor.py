"""Test the Ubiquiti airOS sensors."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airos.const import SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    ap_fixture: dict[str, Any],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_platform(hass, entity_registry, snapshot, Platform.SENSOR)

    # Add explicit assertion
    expected_entity_id = "sensor.nanostation_5ac_ap_name_antenna_gain"
    signal_state = hass.states.get(expected_entity_id)

    assert signal_state is not None, f"Sensor {expected_entity_id} was not created"
    assert signal_state.state == "13", f"Expected state 13, got {signal_state.state}"
    assert signal_state.attributes.get("unit_of_measurement") == "dB", (
        f"Expected unit 'dB', got {signal_state.attributes.get('unit_of_measurement')}"
    )

    freezer.tick(timedelta(seconds=SCAN_INTERVAL.total_seconds() + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # After update, the state should still be the same as the fixture data
    signal_state_after_update = hass.states.get(expected_entity_id)
    assert signal_state_after_update is not None, (
        f"Sensor {expected_entity_id} changed unexpectedly"
    )
    mock_airos_client.status.assert_called()
