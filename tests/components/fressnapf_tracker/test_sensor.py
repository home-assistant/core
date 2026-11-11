"""Test the Fressnapf Tracker sensor platform."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.fressnapf_tracker.PLATFORMS", [Platform.SENSOR]
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("timestamp", "expected_state"),
    [
        pytest.param(
            "2024-01-15T12:30:00", "2024-01-15T12:30:00+00:00", id="no_time_zone"
        ),
        pytest.param(
            "2024-01-15T13:30:00+01:00", "2024-01-15T12:30:00+00:00", id="time_zone"
        ),
        pytest.param("not-a-timestamp", STATE_UNKNOWN, id="invalid"),
        pytest.param("2024-02-30T12:30:00", STATE_UNKNOWN, id="impossible_date"),
        pytest.param(None, STATE_UNKNOWN, id="missing"),
    ],
)
@pytest.mark.usefixtures("mock_auth_client")
async def test_last_seen_timestamp_parsing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
    timestamp: str | None,
    expected_state: str,
) -> None:
    """Test the last seen timestamp is parsed and invalid values are unknown."""
    mock_api_client_init.get_tracker.return_value.last_seen_timestamp = timestamp

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fluffy_last_seen")
    assert state is not None
    assert state.state == expected_state
