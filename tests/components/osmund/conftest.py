"""Common fixtures for the Osmund tests."""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from osmund import ApiKey, Location, PriceDay, PriceInterval
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.osmund.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

CPH = ZoneInfo("Europe/Copenhagen")
KEY = "osm_4f9Kx2Qa_test_only_not_a_real_key"
# The two locations of the API documentation's example: one with access, one without.
OPEN_ID = "0192f3a1-7c2e-7b1a-9d3e-2f6a8c1e4b10"
CLOSED_ID = "0192f3a1-9a41-7d02-8c11-5b7e3d2f6a22"

LOCATIONS = [
    Location(
        id=OPEN_ID,
        label="Hjem",
        state="active",
        api_access="open",
        price_area="DK1",
        meter_resolution="PT1H",
    ),
    Location(
        id=CLOSED_ID,
        label="Sommerhuset",
        state="upcoming",
        api_access="closed",
        price_area="DK2",
        meter_resolution=None,
    ),
]


def price_day(day: date, resolution: str = "PT1H") -> PriceDay:
    """A whole Danish day of made-up prices.

    The hour h costs 1 + h / 100 kr, and its quarter starting at minute m
    1 + h / 100 + m / 10000 kr.
    """
    step = timedelta(minutes=15) if resolution == "PT15M" else timedelta(hours=1)
    intervals = []
    moment = datetime(day.year, day.month, day.day, tzinfo=CPH)
    while moment.date() == day:
        # Step in UTC, so a day with a clock change keeps its 23 or 25 hours.
        end = (moment.astimezone(UTC) + step).astimezone(CPH)
        total = round(1 + moment.hour / 100 + moment.minute / 10000, 4)
        intervals.append(
            PriceInterval(
                start=moment,
                end=end,
                total_inc_vat=total,
                total_ex_vat=round(total / 1.25, 4),
                spot=round(total / 2, 4),
            )
        )
        moment = end
    return PriceDay(
        day=day,
        resolution=resolution,
        complete=True,
        reason=None,
        intervals=tuple(intervals),
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """An Osmund config entry with a made-up key."""
    return MockConfigEntry(domain=DOMAIN, title="Osmund", data={CONF_API_KEY: KEY})


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip setting up the entry."""
    with patch(
        "homeassistant.components.osmund.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """An Osmund client that answers with a key that reads prices, and made-up prices."""
    with (
        patch(
            "homeassistant.components.osmund.OsmundClient", autospec=True
        ) as client_class,
        patch(
            "homeassistant.components.osmund.config_flow.OsmundClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.me.return_value = ApiKey(
            name="Home Assistant",
            prefix="osm_4f9Kx2Qa",
            scopes=frozenset({"prices:read"}),
            expires_at=None,
        )
        client.locations.return_value = LOCATIONS
        client.prices.side_effect = lambda _location_id, day, resolution: price_day(
            day, resolution
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> MockConfigEntry:
    """Set up the Osmund integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
