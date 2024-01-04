"""Test helpers for Husqvarna Automower."""
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.model import MowerAttributes, MowerList
from aioautomower.session import AutomowerSession
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_integration

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


@pytest.fixture(scope="session")
def load_mower_fixture():
    """Load Fixture data."""
    return load_json_value_fixture("mower.json", DOMAIN)


@pytest.fixture(scope="session")
def mower_list_fixture(load_mower_fixture):
    """Generate a mower fixture object."""
    mower = load_mower_fixture
    mowers_list = MowerList(**mower)
    mowers = {}
    for mower in mowers_list.data:
        mowers[mower.id] = mower.attributes
    return mowers


@pytest.fixture(scope="session")
def activity():
    """Defaults value for activity."""
    return "PARKED_IN_CS"


@pytest.fixture(scope="session")
def state():
    """Defaults value for state."""
    return "RESTRICTED"


@pytest.fixture
async def setup_entity(hass: HomeAssistant, mower_list_fixture, activity, state):
    """Set up entity and config entry."""

    mower_data: MowerAttributes = mower_list_fixture[TEST_MOWER_ID]
    if activity:
        mower_data.mower.activity = activity
    if state:
        mower_data.mower.state = state
    config_entry: MockConfigEntry = await setup_integration(hass)
    config_entry.add_to_hass(hass)
    token_decoded = load_fixture("token_decoded.json", DOMAIN)
    with patch(
        "aioautomower.session.AutomowerSession",
        return_value=AsyncMock(
            name="AutomowerMockSession",
            model=AutomowerSession,
            data=mower_list_fixture,
            register_data_callback=MagicMock(),
            unregister_data_callback=MagicMock(),
            connect=AsyncMock(),
            resume_schedule=AsyncMock(),
        ),
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session",
        return_value=AsyncMock(),
    ), patch("jwt.decode", return_value=token_decoded), patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_list_fixture,
    ) as mock_impl:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        mock_impl.assert_called_once()

    return config_entry
