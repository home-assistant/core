"""Test DoorBird events."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_webhook_call
from .conftest import DoorbirdMockerType

from tests.typing import ClientSessionGenerator


async def test_doorbell_ring_event(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test a doorbell ring event."""
    doorbird_entry = await doorbird_mocker()
    relay_1_entity_id = "event.mydoorbird_doorbell"
    assert hass.states.get(relay_1_entity_id).state == STATE_UNKNOWN
    client = await hass_client()
    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_doorbell")
    assert hass.states.get(relay_1_entity_id).state != STATE_UNKNOWN


async def test_motion_event(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test a doorbell motion event."""
    doorbird_entry = await doorbird_mocker()
    relay_1_entity_id = "event.mydoorbird_motion"
    assert hass.states.get(relay_1_entity_id).state == STATE_UNKNOWN
    client = await hass_client()
    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_motion")
    assert hass.states.get(relay_1_entity_id).state != STATE_UNKNOWN


async def test_event_entity_ids_after_camera_rename(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the event to camera entity_id mapping follows a camera rename."""
    doorbird_entry = await doorbird_mocker()
    event_entity_ids = doorbird_entry.entry.runtime_data.event_entity_ids
    assert event_entity_ids == {
        "mydoorbird_doorbell": "camera.mydoorbird_last_motion",
        "mydoorbird_motion": "camera.mydoorbird_last_motion",
    }

    entity_registry.async_update_entity(
        "camera.mydoorbird_last_motion", new_entity_id="camera.renamed"
    )
    await hass.async_block_till_done()

    assert event_entity_ids == {
        "mydoorbird_doorbell": "camera.renamed",
        "mydoorbird_motion": "camera.renamed",
    }
