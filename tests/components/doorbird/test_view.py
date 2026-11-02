"""Test DoorBird view."""

from http import HTTPStatus

import pytest
from pytest_homeassistant.common import async_capture_events
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.doorbird.const import API_URL, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_not_found_exception, mock_webhook_call
from .conftest import DoorbirdMockerType


async def test_non_webhook_with_wrong_token(
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test calling the webhook with the wrong token."""
    await doorbird_mocker()
    client = await hass_client()

    response = await client.get(f"{API_URL}/doorbell?token=wrong")
    assert response.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    "schedule_side_effect",
    [
        pytest.param(None, id="schedule"),
        pytest.param(mock_not_found_exception(), id="no_schedule"),
    ],
)
@pytest.mark.parametrize(
    ("event", "expected_entity_id"),
    [
        pytest.param(
            "mydoorbird_doorbell", "image.mydoorbird_last_ring", id="doorbell"
        ),
        pytest.param("mydoorbird_motion", "image.mydoorbird_last_motion", id="motion"),
    ],
)
async def test_webhook_event_entity_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
    schedule_side_effect: Exception | None,
    event: str,
    expected_entity_id: str,
) -> None:
    """Test the fired event carries the image entity matching its event type."""
    doorbird_entry = await doorbird_mocker(schedule_side_effect=schedule_side_effect)
    events = async_capture_events(hass, f"doorbird_{event}")
    client = await hass_client()

    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == expected_entity_id


@pytest.mark.parametrize(
    ("event", "removed_entity_id", "expected_entity_id"),
    [
        pytest.param(
            "mydoorbird_doorbell", "image.mydoorbird_last_ring", None, id="ring"
        ),
        pytest.param(
            "mydoorbird_doorbell",
            "camera.mydoorbird_last_ring",
            "image.mydoorbird_last_ring",
            id="camera",
        ),
    ],
)
async def test_webhook_event_entity_id_after_entity_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    doorbird_mocker: DoorbirdMockerType,
    event: str,
    removed_entity_id: str,
    expected_entity_id: str | None,
) -> None:
    """Test removing an entity only drops the event mappings it owns."""
    # The deprecated camera is only created when it is already registered.
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        "1234ABCD_last_ring",
        suggested_object_id="mydoorbird_last_ring",
    )
    doorbird_entry = await doorbird_mocker()
    assert hass.states.get(removed_entity_id) is not None
    entity_registry.async_remove(removed_entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(removed_entity_id) is None
    events = async_capture_events(hass, f"doorbird_{event}")
    client = await hass_client()

    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == expected_entity_id
