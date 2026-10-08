"""Test DoorBird events."""

from unittest.mock import patch

import pytest

from homeassistant.components.doorbird.event import DoorBirdEventEntity
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_webhook_call
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


@pytest.mark.parametrize("event", ["mydoorbird_doorbell", "mydoorbird_motion"])
@pytest.mark.parametrize(
    ("renamed_entity_id", "expected_entity_id"),
    [
        pytest.param(
            "camera.mydoorbird_last_motion", "camera.renamed", id="event_camera"
        ),
        pytest.param(
            "camera.mydoorbird_live", "camera.mydoorbird_last_motion", id="live"
        ),
        pytest.param(
            "camera.mydoorbird_last_ring",
            "camera.mydoorbird_last_motion",
            id="last_ring",
        ),
    ],
)
async def test_event_entity_id_after_camera_rename(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    event: str,
    renamed_entity_id: str,
    expected_entity_id: str,
) -> None:
    """Test the fired event carries the camera entity_id after a camera rename."""
    doorbird_entry = await doorbird_mocker()
    events = async_capture_events(hass, f"doorbird_{event}")
    client = await hass_client()

    entity_registry.async_update_entity(
        renamed_entity_id, new_entity_id="camera.renamed"
    )
    await hass.async_block_till_done()
    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == expected_entity_id


@pytest.mark.parametrize(
    ("entity_id", "event"),
    [
        pytest.param("event.mydoorbird_doorbell", "mydoorbird_doorbell", id="doorbell"),
        pytest.param("event.mydoorbird_motion", "mydoorbird_motion", id="motion"),
    ],
)
async def test_event_entity_id_change(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    event: str,
) -> None:
    """Test an event entity is renamed in place and still handles events."""
    doorbird_entry = await doorbird_mocker()
    client = await hass_client()

    with patch.object(
        DoorBirdEventEntity,
        "async_added_to_hass",
        autospec=True,
        side_effect=DoorBirdEventEntity.async_added_to_hass,
    ) as mock_added_to_hass:
        entity_registry.async_update_entity(entity_id, new_entity_id="event.renamed")
        await hass.async_block_till_done()

    mock_added_to_hass.assert_not_called()
    assert hass.states.get(entity_id) is None
    assert hass.states.get("event.renamed").state == STATE_UNKNOWN

    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert hass.states.get("event.renamed").state != STATE_UNKNOWN
