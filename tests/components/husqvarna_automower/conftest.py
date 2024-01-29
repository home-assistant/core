"""Test helpers for Husqvarna Automower."""
import time
from unittest.mock import patch

from aioautomower.model import MowerAttributes, MowerList
from aioautomower.utils import mower_list_to_dictionary_dataclass
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.husqvarna_automower.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .const import TEST_CLIENT_ID, TEST_CLIENT_SECRET

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

TEST_MOWERLIST = load_json_value_fixture("mower.json", DOMAIN)
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


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(load_jwt_fixture, expires_at: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": load_jwt_fixture,
                "scope": "iam:read amc:api",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": expires_at,
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
def mower_list_fixture(load_mower_fixture) -> MowerList:
    """Generate a mower fixture object."""
    mower = load_mower_fixture
    mowers_list = MowerList(**mower)
    mowers = {}
    for mower in mowers_list.data:
        mowers[mower.id] = mower.attributes
    return mowers


@pytest.fixture(scope="session")
def mower_data() -> dict[str, MowerAttributes]:
    """Generate a mower fixture object."""
    return mower_list_to_dictionary_dataclass(TEST_MOWERLIST)


@pytest.fixture(name="activity")
def activity() -> str:
    """Defaults value for activity."""
    return "PARKED_IN_CS"


@pytest.fixture(name="state")
def state() -> str:
    """Defaults value for state."""
    return "RESTRICTED"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(TEST_CLIENT_ID, TEST_CLIENT_SECRET),
    )


@pytest.fixture
async def setup_entity(
    hass: HomeAssistant,
    mower_list_fixture: MowerList,
    mock_config_entry: MockConfigEntry,
    activity,
    state,
):
    """Set up entity and config entry."""

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            TEST_CLIENT_ID,
            TEST_CLIENT_SECRET,
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    mower_data = mower_list_fixture
    test_mower: MowerAttributes = mower_data[TEST_MOWER_ID]
    test_mower.mower.activity = activity
    test_mower.mower.state = state

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
