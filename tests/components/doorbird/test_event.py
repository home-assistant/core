"""Test DoorBird events."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

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
