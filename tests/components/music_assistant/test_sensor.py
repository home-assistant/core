"""Test Music Assistant sensor entities."""

from datetime import timedelta
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .common import setup_integration_from_fixtures, snapshot_music_assistant_entities

from tests.common import async_fire_time_changed


async def test_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test sensor entities."""
    music_assistant_client.send_command.return_value = "http://mock-party-url"
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.SENSOR)


async def test_sensor_url_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test sensor updates URL when timer expires."""
    music_assistant_client.send_command.return_value = "http://mock-party-url-1"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    state = hass.states.get("sensor.party_mode_plugin_guest_url")
    assert state
    assert state.state == "http://mock-party-url-1"

    # Simulate URL change
    music_assistant_client.send_command.return_value = "http://mock-party-url-2"

    # Fast forward time to trigger periodic update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.party_mode_plugin_guest_url")
    assert state
    assert state.state == "http://mock-party-url-2"
