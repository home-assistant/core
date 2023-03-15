"""Tests for diagnostics platform of local calendar."""

from freezegun import freeze_time

from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY, ClientFixture

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

TEST_ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTAMP:20230313T190500
UID:***
DTSTART:19970714T110000
DTEND:19970714T220000
SUMMARY:***
CREATED:20230313T190500
SEQUENCE:***
END:VEVENT
END:VCALENDAR"""


@freeze_time("2023-03-13 12:05:00-07:00")
async def test_empty_calendar(
    hass: HomeAssistant,
    setup_integration: None,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics against an empty calendar."""
    data = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert data == {
        "system_timezone": "tzlocal()",  # Will by python system timezone
        "timezone": "America/Regina",  # HomeAssistant timezone set by fixture
        "now": "2023-03-13T13:05:00-06:00",
        "ics": "",
    }


@freeze_time("2023-03-13 12:05:00-07:00")
async def test_api_date_time_event(
    hass: HomeAssistant,
    setup_integration: None,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    ws_client: ClientFixture,
) -> None:
    """Test an event with a start/end date time."""

    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            "entity_id": TEST_ENTITY,
            "event": {
                "summary": "Bastille Day Party",
                "dtstart": "1997-07-14T17:00:00+00:00",
                "dtend": "1997-07-15T04:00:00+00:00",
            },
        },
    )

    data = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert data == {
        "system_timezone": "tzlocal()",
        "timezone": "America/Regina",
        "now": "2023-03-13T13:05:00-06:00",
        "ics": TEST_ICS,
    }
