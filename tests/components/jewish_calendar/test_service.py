"""Test jewish calendar service."""

import datetime as dt

from freezegun import freeze_time
import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("test_time", "service_data", "expected"),
    [
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                "date": dt.date(2025, 3, 20),
                "nusach": "sfarad",
                "language": "he",
                "is_after_sunset": False,
            },
            "",
            id="no_blessing",
        ),
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                "date": dt.date(2025, 5, 20),
                "nusach": "ashkenaz",
                "language": "he",
                "is_after_sunset": False,
            },
            "היום שבעה ושלושים יום שהם חמישה שבועות ושני ימים בעומר",
            id="ahskenaz-hebrew",
        ),
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                "date": dt.date(2025, 5, 20),
                "nusach": "sfarad",
                "language": "en",
                "is_after_sunset": True,
            },
            "Today is the thirty-eighth day, which are five weeks and three days of the Omer",
            id="sefarad-english-after-sunset",
        ),
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                "date": dt.date(2025, 5, 20),
                "nusach": "sfarad",
                "language": "en",
                "is_after_sunset": False,
            },
            "Today is the thirty-seventh day, which are five weeks and two days of the Omer",
            id="sefarad-english-before-sunset",
        ),
        pytest.param(
            dt.datetime(2025, 5, 20, 21, 0),
            {"nusach": "sfarad", "language": "en"},
            "Today is the thirty-eighth day, which are five weeks and three days of the Omer",
            id="sefarad-english-after-sunset-without-date",
        ),
        pytest.param(
            dt.datetime(2025, 5, 20, 6, 0),
            {
                "nusach": "sfarad",
            },
            "היום שבעה ושלושים יום שהם חמישה שבועות ושני ימים לעומר",
            id="sefarad-english-before-sunset-without-date",
        ),
    ],
    indirect=["test_time"],
)
async def test_get_omer_blessing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    test_time: dt.date | None,
    service_data: object,
    expected: str,
) -> None:
    """Test get omer blessing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async def call_service():
        return await hass.services.async_call(
            DOMAIN,
            "count_omer",
            service_data,
            blocking=True,
            return_response=True,
        )

    if test_time:
        with freeze_time(test_time):
            result = await call_service()
    else:
        result = await call_service()

    assert result["message"] == expected
