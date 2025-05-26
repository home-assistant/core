"""Test jewish calendar service."""

import datetime as dt

import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("test_time", "service_data", "expected"),
    [
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                "date": dt.date(2025, 3, 20),
                "nusach": "sfarad",
                "language": "he",
                "after_sunset": False,
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
                "after_sunset": False,
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
                "after_sunset": True,
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
                "after_sunset": False,
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
            {"nusach": "sfarad"},
            "היום שבעה ושלושים יום שהם חמישה שבועות ושני ימים לעומר",
            id="sefarad-english-before-sunset-without-date",
        ),
    ],
    indirect=["test_time"],
)
@pytest.mark.usefixtures("setup_at_time")
async def test_get_omer_blessing(
    hass: HomeAssistant, service_data: dict[str, str | dt.date | bool], expected: str
) -> None:
    """Test get omer blessing."""

    result = await hass.services.async_call(
        DOMAIN,
        "count_omer",
        service_data,
        blocking=True,
        return_response=True,
    )

    assert result["message"] == expected
