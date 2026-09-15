"""Test the MobilityData sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import make_arrival, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor states and attributes via snapshot."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_second_departure_unknown_with_single_arrival(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test the following sensor is unknown when only one departure exists."""
    mock_handle.get_arrivals.return_value = [make_arrival("S1", 5)]
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.1st_grand_next_departure").state
        == "2026-08-01T08:05:30+00:00"
    )
    assert hass.states.get("sensor.1st_grand_second_departure").state == "unknown"
    assert hass.states.get("sensor.1st_grand_third_departure").state == "unknown"
