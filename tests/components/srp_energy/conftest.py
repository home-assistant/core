"""Fixtures for Srp Energy integration tests."""
from __future__ import annotations

from collections.abc import Generator
import datetime as dt
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.srp_energy import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import ACCNT_ID, MOCK_USAGE, TEST_DATE, TEST_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture(name="hass_time_zone")
def fixture_hass_time_zone() -> str:
    """Return default hass timezone."""
    return "America/Phoenix"


@pytest.fixture(name="setup_hass_config", autouse=True)
def fixture_setup_hass_config(hass, hass_time_zone) -> None:
    """Set up things to be run when tests are started."""
    hass.config.latitude = 33.27
    hass.config.longitude = 112
    hass.config.set_time_zone(hass_time_zone)


@pytest.fixture(name="hass_tz_info")
def fixture_hass_tz_info(hass) -> dt.tzinfo | None:
    """Return timezone info for the hass timezone."""
    return dt_util.get_time_zone(hass.config.time_zone)


@pytest.fixture(name="no_urllib", autouse=True)
def fixture_no_urllib(capsys) -> Generator:
    """Check for urllib calls."""
    print("Load no_urllib fixture")
    yield
    print("no_urllib Checking for url call")
    captured = capsys.readouterr()
    print(captured.err)
    assert "myaccount.srpnet.com" not in captured.err


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_USER_INPUT[CONF_NAME],
        domain=DOMAIN,
        data=TEST_USER_INPUT,
        unique_id=ACCNT_ID,
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
    hass_tz_info: dt.tzinfo,
    mock_config_entry: MockConfigEntry,
    mock_srp_energy,
    mock_srp_energy_config_flow,
) -> MockConfigEntry:
    """Set up the Srp Energy integration for testing."""
    freezer.move_to(TEST_DATE)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
