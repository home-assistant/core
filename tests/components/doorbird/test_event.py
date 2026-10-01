"""Test DoorBird events."""

import pytest

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback

from . import mock_not_found_exception, mock_webhook_call
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


@pytest.mark.parametrize(
    ("event", "expected_entity_id"),
    [
        pytest.param(
            "mydoorbird_doorbell", "image.mydoorbird_last_ring", id="doorbell"
        ),
        pytest.param("mydoorbird_motion", "image.mydoorbird_last_motion", id="motion"),
    ],
)
async def test_event_data_points_at_matching_image_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
    event: str,
    expected_entity_id: str,
) -> None:
    """The fired event carries the image entity matching its event type."""
    doorbird_entry = await doorbird_mocker()
    events: list[Event] = []

    @callback
    def _capture(fired_event: Event) -> None:
        events.append(fired_event)

    hass.bus.async_listen(f"{DOMAIN}_{event}", _capture)

    client = await hass_client()
    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == expected_entity_id


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

    events: list[Event] = []

    @callback
    def _capture(fired_event: Event) -> None:
        events.append(fired_event)

    hass.bus.async_listen(f"{DOMAIN}_mydoorbird_doorbell", _capture)

    client = await hass_client()
    await mock_webhook_call(doorbird_entry.entry, client, "mydoorbird_doorbell")
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == "image.mydoorbird_last_ring"
