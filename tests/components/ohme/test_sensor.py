"""Tests for sensors."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from ohme import ApiException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Ohme sensors."""
    with patch("homeassistant.components.ohme.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    entity_entries = sorted(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id),
        key=lambda entry: entry.entity_id,
    )
    assert entity_entries

    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_entry.disabled_by is None, "Please enable all entities."
        state = hass.states.get(entity_entry.entity_id)
        assert state, f"State not found for {entity_entry.entity_id}"
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_sensors_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that sensors show as unavailable after a coordinator failure."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.ohme_home_pro_energy")
    assert state.state == "1.0"

    mock_client.async_get_charge_session.side_effect = ApiException
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.ohme_home_pro_energy")
    assert state.state == STATE_UNAVAILABLE

    mock_client.async_get_charge_session.side_effect = None
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.ohme_home_pro_energy")
    assert state.state == "1.0"


async def test_summary_failure_nonfatal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test summary failures don't block setup of the live charger sensors."""
    mock_client.async_get_charge_summary.side_effect = ApiException

    await setup_integration(hass, mock_config_entry)

    live_state = hass.states.get("sensor.ohme_home_pro_energy")
    assert live_state
    assert live_state.state == "1.0"
    assert hass.states.get("sensor.ohme_home_pro_total_charged_energy") is None
