"""Test helpers for Husqvarna Automower."""
from collections.abc import Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.model import MowerAttributes, MowerList
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

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"
USER_ID = "123"
CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


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


@pytest.fixture
def activity() -> str:
    """Defaults value for activity."""
    return "PARKED_IN_CS"


@pytest.fixture
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
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
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
            CLIENT_ID,
            CLIENT_SECRET,
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


@pytest.fixture
def mock_wled(
    mower_list_fixture: MowerList,
) -> Generator[MagicMock, None, None]:
    """Return a mocked WLED client."""
    mower_data = mower_list_fixture

    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator",
        autospec=True,
    ) as wled_mock:
        wled_mock.return_value._async_update_data.return_value = mower_data
        wled_mock.listen = AsyncMock()
        yield wled_mock
