"""Test the Sonarr calendar entity."""
from http import HTTPStatus

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_calendar(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    hass_client,
) -> None:
    """Test the API returns the Sonarr calendar."""
    client = await hass_client()
    response = await client.get("/api/calendars")
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data == [
        {
            "entity_id": "calendar.sonarr_episodes",
            "name": "Sonarr Episodes",
        }
    ]


async def test_get_episodes(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_client
) -> None:
    """Test data is extracted from the coordinator."""
    client = await hass_client()
    response = await client.get(
        "/api/calendars/calendar.sonarr_episodes?start=2014-01-26&end=2014-01-28"
    )
    assert response.status == HTTPStatus.OK
    events = await response.json()
    assert len(events) == 1
