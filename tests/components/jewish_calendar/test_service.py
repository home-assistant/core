"""Test jewish calendar service."""

import datetime as dt

from hdate.translator import Language
import pytest

from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("test_date", "nusach", "language", "expected"),
    [
        pytest.param(dt.date(2025, 3, 20), "sfarad", "he", "", id="no_blessing"),
        pytest.param(
            dt.date(2025, 5, 20),
            "ashkenaz",
            "he",
            "היום שבעה ושלושים יום שהם חמישה שבועות ושני ימים בעומר",
            id="ahskenaz-hebrew",
        ),
        pytest.param(
            dt.date(2025, 5, 20),
            "sfarad",
            "en",
            "Today is the thirty-seventh day, which are five weeks and two days of the Omer",
            id="sefarad-english",
        ),
    ],
)
async def test_get_omer_blessing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    test_date: dt.date,
    nusach: str,
    language: Language,
    expected: str,
) -> None:
    """Test get omer blessing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN,
        "count_omer",
        {"date": test_date, "nusach": nusach, "language": language},
        blocking=True,
        return_response=True,
    )

    assert result["message"] == expected
