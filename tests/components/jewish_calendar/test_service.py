"""Test jewish calendar service."""

import datetime as dt

import pytest

from homeassistant.components.jewish_calendar.const import (
    ATTR_AFTER_SUNSET,
    ATTR_DATE,
    ATTR_NUSACH,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("test_time", "service_data", "expected"),
    [
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                ATTR_DATE: dt.date(2025, 3, 20),
                ATTR_NUSACH: "sfarad",
                CONF_LANGUAGE: "he",
                ATTR_AFTER_SUNSET: False,
            },
            "",
            id="no_blessing",
        ),
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                ATTR_DATE: dt.date(2025, 5, 20),
                ATTR_NUSACH: "ashkenaz",
                CONF_LANGUAGE: "he",
                ATTR_AFTER_SUNSET: False,
            },
            "היום שבעה ושלושים יום שהם חמישה שבועות ושני ימים בעומר",
            id="ahskenaz-hebrew",
        ),
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                ATTR_DATE: dt.date(2025, 5, 20),
                ATTR_NUSACH: "sfarad",
                CONF_LANGUAGE: "en",
                ATTR_AFTER_SUNSET: True,
            },
            "Today is the thirty-eighth day, which are five weeks and three days of the Omer",
            id="sefarad-english-after-sunset",
        ),
        pytest.param(
            dt.datetime(2025, 3, 20, 21, 0),
            {
                ATTR_DATE: dt.date(2025, 5, 20),
                ATTR_NUSACH: "sfarad",
                CONF_LANGUAGE: "en",
                ATTR_AFTER_SUNSET: False,
            },
            "Today is the thirty-seventh day, which are five weeks and two days of the Omer",
            id="sefarad-english-before-sunset",
        ),
        pytest.param(
            dt.datetime(2025, 5, 20, 21, 0),
            {ATTR_NUSACH: "sfarad", CONF_LANGUAGE: "en"},
            "Today is the thirty-eighth day, which are five weeks and three days of the Omer",
            id="sefarad-english-after-sunset-without-date",
        ),
        pytest.param(
            dt.datetime(2025, 5, 20, 6, 0),
            {ATTR_NUSACH: "sfarad"},
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
