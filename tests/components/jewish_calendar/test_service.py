"""Test jewish calendar service."""

import datetime as dt
from unittest.mock import patch

from hdate import HebrewDate, Months
from hdate.translator import Language
import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("test_date", "nusach", "language", "is_after_sunset", "expected"),
    [
        pytest.param(dt.date(2025, 3, 20), "sfarad", "he", False, "", id="no_blessing"),
        pytest.param(
            dt.date(2025, 5, 20),
            "ashkenaz",
            "he",
            False,
            "היום שבעה ושלושים יום שהם חמישה שבועות ושני ימים בעומר",
            id="ahskenaz-hebrew",
        ),
        pytest.param(
            dt.date(2025, 5, 20),
            "sfarad",
            "en",
            True,
            "Today is the thirty-eighth day, which are five weeks and three days of the Omer",
            id="sefarad-english",
        ),
        pytest.param(
            None,  # Test case where date is not provided
            "sfarad",
            "en",
            False,
            "Today is the thirteenth day, which are one week and six days of the Omer",
            id="no_date_provided",
        ),
        pytest.param(
            None,  # Test case where date is not provided and it's after sunset
            "adot_mizrah",
            "he",
            True,  # Ignored
            "היום שלושה עשר יום לעומר שהם שבוע אחד ושישה ימים",
            id="no_date_after_sunset",
        ),
    ],
)
async def test_get_omer_blessing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    test_date: dt.date | None,
    nusach: str,
    language: Language,
    is_after_sunset: bool,
    expected: str,
) -> None:
    """Test get omer blessing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.jewish_calendar.service.get_hebrew_date"
    ) as mock_date:
        mock_date.return_value = HebrewDate(5785, Months.NISAN, 28)
        service_data = {
            "nusach": nusach,
            "language": language,
            "is_after_sunset": is_after_sunset,
        }
        if test_date:
            service_data["date"] = test_date

        result = await hass.services.async_call(
            DOMAIN,
            "count_omer",
            service_data,
            blocking=True,
            return_response=True,
        )

        assert result["message"] == expected
