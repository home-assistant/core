"""Test Music Assistant image entities."""

from datetime import timedelta
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .common import setup_integration_from_fixtures, snapshot_music_assistant_entities

from tests.common import async_fire_time_changed


async def test_image_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    music_assistant_client: MagicMock,
) -> None:
    """Test image entities."""
    music_assistant_client.send_command.return_value = "http://mock-party-url"
    await setup_integration_from_fixtures(hass, music_assistant_client)
    snapshot_music_assistant_entities(hass, entity_registry, snapshot, Platform.IMAGE)


async def test_image_url_update(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test image updates when URL changes."""
    music_assistant_client.send_command.return_value = "http://mock-party-url-1"
    await setup_integration_from_fixtures(hass, music_assistant_client)

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    last_updated = state.state
    assert last_updated is not None

    # Simulate URL change
    music_assistant_client.send_command.return_value = "http://mock-party-url-2"

    # Fast forward time to trigger periodic update
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
    await hass.async_block_till_done()

    state = hass.states.get("image.party_mode_plugin_guest_qr_code")
    assert state
    assert state.state != last_updated
