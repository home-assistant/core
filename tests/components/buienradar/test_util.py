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
        ("2026-01-01T05:30:00+00:00", True),
        ("2026-01-01T06:30:00+00:00", False),
    ],
    ids=["daytime", "midnight_hour"],
)
async def test_unparsable_data_is_quiet_during_the_midnight_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    frozen_time: str,
    expect_warning: bool,
) -> None:
    """Test the parse failure warning is suppressed in the midnight hour.

    Buienradar is known to serve no data around midnight, so the warning is
    only interesting for the rest of the day. The configured time zone is what
    decides that, which is why the times below are UTC but the hour that
    matters is the one in America/Regina (UTC-6, no DST).
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
