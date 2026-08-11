"""Tests for the Buienradar utilities."""

from unittest.mock import AsyncMock, patch

from buienradar.constants import CONTENT, MESSAGE, STATUS_CODE, SUCCESS
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.buienradar.util import BrData
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

WARNING = "Unable to parse data from Buienradar"


@pytest.mark.parametrize(
    ("frozen_time", "expect_warning"),
    [
        ("2026-01-14T23:00:00+00:00", False),
        ("2026-01-14T23:59:59+00:00", False),
        ("2026-01-15T00:00:00+00:00", True),
        ("2026-07-14T22:30:00+00:00", False),
        ("2026-01-15T06:30:00+00:00", True),
    ],
    ids=[
        "cet_0000_start_of_quiet_hour",
        "cet_0059_end_of_quiet_hour",
        "cet_0100_just_after",
        "cest_0030_quiet_hour_in_dst",
        "cet_0730_quiet_only_where_user_lives",
    ],
)
async def test_unparsable_data_is_quiet_during_the_midnight_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    frozen_time: str,
    expect_warning: bool,
) -> None:
    """Test the parse failure warning is suppressed in the midnight hour.

    buienradar.nl serves no data while it updates its forecast between 00:00 and
    01:00 CE(S)T, so the warning is only interesting outside that hour. The hour
    that decides this belongs to the service, so the configured time zone here is
    deliberately somewhere else: America/Regina is UTC-6 with no DST, which puts
    every case below in a different hour locally than in Amsterdam.

    The times are UTC. The first three pin the edges of the quiet hour in CET,
    the fourth repeats it in CEST so the offset is not hardcoded, and the last
    one is the quiet hour in America/Regina rather than in Amsterdam, so it must
    still warn.
    """
    await hass.config.async_set_time_zone("America/Regina")
    freezer.move_to(frozen_time)

    data = BrData(hass, {CONF_LATITUDE: 51.5, CONF_LONGITUDE: 5.5}, 60, [])
    fetched = {SUCCESS: True, CONTENT: "{}", STATUS_CODE: 200}

    with (
        patch.object(BrData, "get_data", new=AsyncMock(return_value=fetched)),
        patch(
            "homeassistant.components.buienradar.util.parse_data",
            return_value={SUCCESS: False, MESSAGE: "no data"},
        ),
    ):
        assert await data._async_update() is None

    assert (WARNING in caplog.text) is expect_warning
