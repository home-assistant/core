"""Tests for the Buienradar utilities."""

import datetime
from http import HTTPStatus
from unittest.mock import patch

from buienradar.constants import MESSAGE, SUCCESS
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_LATITUDE = 51.5
TEST_LONGITUDE = 5.5
TEST_CFG_DATA = {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}

WARNING = "Unable to parse data from Buienradar"


@pytest.mark.parametrize(
    ("update_at", "expect_warning"),
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
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    update_at: str,
    expect_warning: bool,
) -> None:
    """Test the parse failure warning is suppressed in the midnight hour.

    buienradar.nl serves no data while it updates its forecast between 00:00 and
    01:00 CE(S)T, so the warning is only interesting outside that hour. The hour
    that decides this belongs to the service, so the configured time zone here is
    deliberately somewhere else: America/Regina is UTC-6 with no DST, which puts
    every case below in a different hour locally than in Amsterdam.

    The times are UTC. The first three pin the edges of the quiet hour in CET,
    the fourth repeats it in CEST so the offset is not assumed, and the last one
    is the quiet hour in America/Regina rather than in Amsterdam, so it must
    still warn.
    """
    await hass.config.async_set_time_zone("America/Regina")
    aioclient_mock.get(
        "https://data.buienradar.nl/2.0/feed/json", status=HTTPStatus.OK, text="{}"
    )
    aioclient_mock.get(
        f"https://gps.buienradar.nl/getrr.php?lat={TEST_LATITUDE}&lon={TEST_LONGITUDE}",
        status=HTTPStatus.OK,
        text="",
    )

    update = dt_util.parse_datetime(update_at)
    assert update is not None
    # A failed update reschedules itself two minutes later, which is the update
    # the assertion below is about.
    freezer.move_to(update - datetime.timedelta(minutes=2))

    entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.buienradar.util.parse_data",
        return_value={SUCCESS: False, MESSAGE: "no data"},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        caplog.clear()
        freezer.move_to(update)
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

    assert (WARNING in caplog.text) is expect_warning
