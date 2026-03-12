"""Fixtures for Srp Energy integration tests."""

from collections.abc import Generator
import datetime as dt
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.srp_energy.const import DOMAIN, PHOENIX_TIME_ZONE
from homeassistant.components.srp_energy.coordinator import HourlyUsageTuple
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MOCK_USAGE_AT_TIMES, TEST_CONFIG_HOME

from tests.common import MockConfigEntry

PHOENIX_ZONE_INFO = dt_util.get_time_zone(PHOENIX_TIME_ZONE)


@pytest.fixture(name="setup_hass_config")
async def fixture_setup_hass_config(hass: HomeAssistant) -> None:
    """Set up things to be run when tests are started."""
    hass.config.latitude = 33.27
    hass.config.longitude = 112
    await hass.config.async_set_time_zone(PHOENIX_TIME_ZONE)


@pytest.fixture(name="hass_tz_info")
def fixture_hass_tz_info(hass: HomeAssistant, setup_hass_config) -> dt.tzinfo | None:
    """Return timezone info for the hass timezone."""
    return dt_util.get_time_zone(hass.config.time_zone)


@pytest.fixture(name="test_date")
def fixture_test_date(hass: HomeAssistant, hass_tz_info) -> dt.datetime | None:
    """Return test datetime for the hass timezone."""
    # Default to run in the middle of the day on aug 2
    return dt.datetime(2022, 8, 2, 12, 0, 0, 0, tzinfo=hass_tz_info)


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=TEST_CONFIG_HOME, unique_id=TEST_CONFIG_HOME[CONF_ID]
    )


def _mock_usage(
    start_date: dt.datetime, end_date: dt.datetime, is_tou: bool
) -> list[HourlyUsageTuple]:
    now = dt_util.now(PHOENIX_ZONE_INFO).replace(minute=0, second=0, microsecond=0)
    data = MOCK_USAGE_AT_TIMES[-1][1]
    start_date = start_date.replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=PHOENIX_ZONE_INFO
    )
    end_date = end_date.replace(
        hour=23, minute=59, second=59, microsecond=999999, tzinfo=PHOENIX_ZONE_INFO
    )
    for key, value in reversed(MOCK_USAGE_AT_TIMES):
        if now >= dt_util.parse_datetime(key).replace(tzinfo=PHOENIX_ZONE_INFO):
            data = value
            break

    def is_in_range(ts: str) -> bool:
        item_time = dt_util.parse_datetime(ts).replace(tzinfo=PHOENIX_ZONE_INFO)
        after_start = item_time >= start_date
        before_end = item_time <= end_date
        return after_start and before_end

    return [item for item in data if is_in_range(item[2])]


@pytest.fixture(name="mock_srp_energy")
def fixture_mock_srp_energy() -> Generator[MagicMock]:
    """Return a mocked SrpEnergyClient client."""
    with patch(
        "homeassistant.components.srp_energy.SrpEnergyClient", autospec=True
    ) as srp_energy_mock:
        client = srp_energy_mock.return_value
        client.validate.return_value = True
        client.usage.side_effect = _mock_usage
        yield client


@pytest.fixture(name="mock_srp_energy_config_flow")
def fixture_mock_srp_energy_config_flow() -> Generator[MagicMock]:
    """Return a mocked config_flow SrpEnergyClient client."""
    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient", autospec=True
    ) as srp_energy_mock:
        client = srp_energy_mock.return_value
        client.validate.return_value = True
        client.usage.side_effect = _mock_usage
        yield client


@pytest.fixture
async def init_integration(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    test_date: dt.datetime,
    mock_config_entry: MockConfigEntry,
    mock_srp_energy,
    mock_srp_energy_config_flow,
) -> MockConfigEntry:
    """Set up the Srp Energy integration for testing."""
    freezer.move_to(test_date)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.srp_energy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
