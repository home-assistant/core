"""Fixtures for Srp Energy integration tests."""

from __future__ import annotations

from collections.abc import Generator
import datetime as dt
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.srp_energy.const import DOMAIN, PHOENIX_TIME_ZONE
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import MOCK_USAGE, TEST_CONFIG_HOME

from tests.common import MockConfigEntry


@pytest.fixture(name="setup_hass_config", autouse=True)
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
    return dt.datetime(2022, 8, 2, 0, 0, 0, 0, tzinfo=hass_tz_info)


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=TEST_CONFIG_HOME, unique_id=TEST_CONFIG_HOME[CONF_ID]
    )


@pytest.fixture(name="mock_srp_energy")
def fixture_mock_srp_energy() -> Generator[None, MagicMock, None]:
    """Return a mocked SrpEnergyClient client."""
    with patch(
        "homeassistant.components.srp_energy.SrpEnergyClient", autospec=True
    ) as srp_energy_mock:
        client = srp_energy_mock.return_value
        client.validate.return_value = True
        client.usage.return_value = MOCK_USAGE
        yield client


@pytest.fixture(name="mock_srp_energy_config_flow")
def fixture_mock_srp_energy_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked config_flow SrpEnergyClient client."""
    with patch(
        "homeassistant.components.srp_energy.config_flow.SrpEnergyClient", autospec=True
    ) as srp_energy_mock:
        client = srp_energy_mock.return_value
        client.validate.return_value = True
        client.usage.return_value = MOCK_USAGE
        yield client


@pytest.fixture
async def init_integration(
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
