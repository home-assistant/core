"""Tests for the Qube Heat Pump binary sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all binary sensor entities via snapshot."""
    with patch(
        "homeassistant.components.hr_energy_qube.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError("Connection lost"), None),
        (None, None),
    ],
)
async def test_binary_sensor_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception | None,
    return_value: None,
) -> None:
    """Test binary sensors become unavailable when coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    # Verify binary sensors are available after setup
    states = hass.states.async_all("binary_sensor")
    assert len(states) > 0
    assert all(s.state != STATE_UNAVAILABLE for s in states)

    # Make the next fetch fail
    mock_qube_client.get_all_data = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )

    # Skip time to trigger coordinator refresh
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # All binary sensors should be unavailable
    states = hass.states.async_all("binary_sensor")
    assert all(s.state == STATE_UNAVAILABLE for s in states)
