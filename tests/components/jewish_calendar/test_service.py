"""Test jewish calendar service."""

import datetime as dt
from datetime import UTC
from unittest import mock

from freezegun.api import FrozenDateTimeFactory
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


@pytest.mark.parametrize(
    ("test_time", "sunset", "expected"),
    [
        pytest.param(
            dt.datetime(2025, 4, 20, 19, 10, tzinfo=UTC),
            dt.datetime(2025, 4, 20, 19, 15, tzinfo=UTC),
            "היום שבעה ימים שהם שבוע אחד לעומר",
            id="before-sunset",
        ),
        pytest.param(
            dt.datetime(2025, 4, 20, 19, 20, tzinfo=UTC),
            dt.datetime(2025, 4, 20, 19, 15, tzinfo=UTC),
            "היום שמונה ימים שהם שבוע אחד ויום אחד לעומר",
            id="after-sunset",
        ),
    ],
)
@mock.patch("homeassistant.components.jewish_calendar.service.get_astral_event_date")
async def test_get_current_omer_blessing(
    mock_get_astral_event_date: mock.MagicMock,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    test_time: dt.datetime,
    sunset: dt.datetime,
    expected: str,
) -> None:
    """Test get omer blessing of current time."""
    hass.config.time_zone = "UTC"
    freezer.move_to(test_time)
    mock_get_astral_event_date.return_value = sunset
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN,
        "count_omer",
        {"nusach": "sfarad", "language": "he"},
        blocking=True,
        return_response=True,
    )

    assert result["message"] == expected
