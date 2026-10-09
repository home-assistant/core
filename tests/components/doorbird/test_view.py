"""Test DoorBird view."""

from http import HTTPStatus

import pytest

from homeassistant.components.doorbird.const import API_URL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import mock_webhook_call
from .conftest import DoorbirdMockerType

from tests.common import async_capture_events
from tests.typing import ClientSessionGenerator


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
    event: str,
    expected_entity_id: str,
) -> None:
    """Test the fired event carries the image entity matching its event type."""
    doorbird_entry = await doorbird_mocker()
    events = async_capture_events(hass, f"doorbird_{event}")
    client = await hass_client()

    await mock_webhook_call(doorbird_entry.entry, client, event)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[ATTR_ENTITY_ID] == expected_entity_id
