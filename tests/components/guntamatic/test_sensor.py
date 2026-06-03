"""Tests for the Guntamatic sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from guntamatic.heater import NoSerialException
import pytest
import requests
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.guntamatic.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_heater")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.guntamatic._PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


@pytest.mark.parametrize(
    "side_effect",
    [
        requests.exceptions.ConnectionError("Connection lost"),
        NoSerialException,
        Exception("Unknown error"),
    ],
)
async def test_state_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    side_effect: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors handle failures."""
    await setup_integration(hass, mock_config_entry)

    mock_heater.parse_data.side_effect = side_effect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_title_boiler_temperature")
    assert state.state == STATE_UNAVAILABLE

    # Recovery
    mock_heater.parse_data.side_effect = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.mock_title_boiler_temperature")
    assert state.state != STATE_UNAVAILABLE
