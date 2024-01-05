"""Test helpers for Husqvarna Automower."""
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.model import MowerAttributes, MowerList
from aioautomower.session import AutomowerSession
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"
USER_ID = "123"


@pytest.fixture(scope="session")
def load_jwt_fixture():
    """Load Fixture data."""
    return load_fixture("jwt", DOMAIN)


@pytest.fixture(scope="session")
def load_token_decoded_fixture():
    """Load Fixture data."""
    return load_fixture("token_decoded.json", DOMAIN)


@pytest.fixture
def mock_config_entry(load_jwt_fixture) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": "husqvarna_automower_433e5fdf_5129_452c_ba7f_fadce3213042",
            "token": {
                "access_token": load_jwt_fixture,
                "scope": "iam:read amc:api",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": 1697753347,
            },
        },
        unique_id=USER_ID,
        entry_id="automower_test",
    )


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


@pytest.fixture
def activity():
    """Defaults value for activity."""
    return "PARKED_IN_CS"


@pytest.fixture
def state():
    """Defaults value for state."""
    return "RESTRICTED"


@pytest.fixture
async def setup_entity(
    hass: HomeAssistant,
    mower_list_fixture,
    mock_config_entry,
    load_token_decoded_fixture,
    activity,
    state,
):
    """Set up entity and config entry."""

    mower_data: MowerAttributes = mower_list_fixture[TEST_MOWER_ID]
    mower_data.mower.activity = activity
    mower_data.mower.state = state
    config_entry: MockConfigEntry = mock_config_entry
    config_entry.add_to_hass(hass)
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
    ), patch("jwt.decode", return_value=load_token_decoded_fixture), patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_list_fixture,
    ) as mock_impl:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        mock_impl.assert_called_once()

    return config_entry
