"""Test DoorBird view."""

from http import HTTPStatus

import pytest
from pytest_homeassistant.common import async_capture_events
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.doorbird.const import API_URL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mock_webhook_call
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


@pytest.mark.parametrize("event", ["mydoorbird_doorbell", "mydoorbird_motion"])
async def test_webhook_event_entity_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    doorbird_mocker: DoorbirdMockerType,
    event: str,
) -> None:
    """Test the fired event carries the camera entity_id."""
    doorbird_entry = await doorbird_mocker()
    events = async_capture_events(hass, f"doorbird_{event}")
    client = await hass_client()

    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == "camera.mydoorbird_last_motion"


@pytest.mark.parametrize("event", ["mydoorbird_doorbell", "mydoorbird_motion"])
@pytest.mark.parametrize(
    ("removed_entity_id", "expected_entity_id"),
    [
        pytest.param(
            "camera.mydoorbird_live", "camera.mydoorbird_last_motion", id="live"
        ),
        pytest.param(
            "camera.mydoorbird_last_ring",
            "camera.mydoorbird_last_motion",
            id="last_ring",
        ),
        pytest.param("camera.mydoorbird_last_motion", None, id="last_motion"),
    ],
)
async def test_webhook_event_entity_id_after_camera_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    doorbird_mocker: DoorbirdMockerType,
    event: str,
    removed_entity_id: str,
    expected_entity_id: str | None,
) -> None:
    """Test removing a camera only drops the event mappings it owns."""
    doorbird_entry = await doorbird_mocker()
    entity_registry.async_remove(removed_entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(removed_entity_id) is None
    events = async_capture_events(hass, f"doorbird_{event}")
    client = await hass_client()

    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == expected_entity_id
