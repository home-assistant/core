"""Tests for the Twente Milieu calendar."""
from http import HTTPStatus

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.freeze_time("2022-01-05 00:00:00+00:00")
async def test_waste_pickup_calendar(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Twente Milieu waste pickup calendar."""
    assert (state := hass.states.get("calendar.twente_milieu"))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


async def test_api_calendar(
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the API returns the calendar."""
    client = await hass_client()
    response = await client.get("/api/calendars")
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data == snapshot


async def test_api_events(
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Twente Milieu calendar view."""
    client = await hass_client()
    response = await client.get(
        "/api/calendars/calendar.twente_milieu?start=2022-01-05&end=2022-01-06"
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert len(events) == 1
    assert events == snapshot
