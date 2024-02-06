"""Test helpers for Husqvarna Automower."""
from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from aioautomower.model import MowerAttributes
from aioautomower.utils import mower_list_to_dictionary_dataclass
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import TEST_CLIENT_ID, TEST_CLIENT_SECRET, USER_ID

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


@pytest.fixture(name="jwt")
def load_jwt_fixture():
    """Load Fixture data."""
    return load_fixture("jwt", DOMAIN)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(jwt, expires_at: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": jwt,
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
def mower_data() -> dict[str, MowerAttributes]:
    """Generate a mower fixture object."""
    return mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            TEST_CLIENT_ID,
            TEST_CLIENT_SECRET,
        ),
        DOMAIN,
    )


@pytest.fixture(name="activity")
def activity() -> str:
    """Defaults value for activity."""
    return "PARKED_IN_CS"


@pytest.fixture(name="state")
def state() -> str:
    """Defaults value for state."""
    return "RESTRICTED"


@pytest.fixture
async def setup_entity(
    hass: HomeAssistant,
    mower_data: dict[str, MowerAttributes],
    mock_config_entry: MockConfigEntry,
    activity,
    state,
):
    """Set up entity and config entry."""

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
def mock_automower_client() -> Generator[AsyncMock, None, None]:
    """Mock a Homeassistant Analytics client."""
    with patch(
        "homeassistant.components.husqvarna_automower.AutomowerSession",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_status.return_value = mower_list_to_dictionary_dataclass(
            load_json_value_fixture("mower.json", DOMAIN)
        )
        yield client
