"""Test DoorBird events."""

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import mock_not_found_exception, mock_webhook_call
from .conftest import DoorbirdMockerType

from tests.common import async_capture_events
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


async def test_event_data_entity_id_without_schedule_api(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Models without the schedule API still report the image entity_id.

    They expose no event entities, since those are built from the schedule, but
    the image falls back to the configured events so it still maps.
    """
    doorbird_entry = await doorbird_mocker(
        schedule_side_effect=mock_not_found_exception()
    )
    assert hass.states.async_entity_ids("image") == [
        "image.mydoorbird_last_motion",
        "image.mydoorbird_last_ring",
    ]
    assert hass.states.async_entity_ids("event") == []

    events = async_capture_events(hass, f"{DOMAIN}_mydoorbird_doorbell")
    client = await hass_client()
    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_doorbell")
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == "image.mydoorbird_last_ring"
