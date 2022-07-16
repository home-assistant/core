"""Tests for the Twente Milieu calendar."""
from http import HTTPStatus

import pytest

from homeassistant.components.twentemilieu.const import DOMAIN
from homeassistant.const import ATTR_ICON, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2022-01-05 00:00:00+00:00")
async def test_waste_pickup_calendar(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Twente Milieu waste pickup calendar."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("calendar.twente_milieu")
    entry = entity_registry.async_get("calendar.twente_milieu")
    assert entry
    assert state
    assert entry.unique_id == "12345"
    assert state.attributes[ATTR_ICON] == "mdi:delete-empty"
    assert state.attributes["all_day"] is True
    assert state.attributes["message"] == "Christmas tree pickup"
    assert not state.attributes["location"]
    assert not state.attributes["description"]
    assert state.state == STATE_OFF

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "12345")}
    assert device_entry.manufacturer == "Twente Milieu"
    assert device_entry.name == "Twente Milieu"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.configuration_url == "https://www.twentemilieu.nl"
    assert not device_entry.model
    assert not device_entry.sw_version


async def test_api_calendar(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client,
) -> None:
    """Test the API returns the calendar."""
    client = await hass_client()
    response = await client.get("/api/calendars")
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data == [
        {
            "entity_id": "calendar.twente_milieu",
            "name": "Twente Milieu",
        }
    ]


async def test_api_events(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client,
) -> None:
    """Test the Twente Milieu calendar view."""
    client = await hass_client()
    response = await client.get(
        "/api/calendars/calendar.twente_milieu?start=2022-01-05&end=2022-01-06"
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert len(events) == 1
    assert events[0] == {
        "start": {"date": "2022-01-06"},
        "end": {"date": "2022-01-06"},
        "summary": "Christmas tree pickup",
        "description": None,
        "location": None,
    }
