"""Common fixtures for the A. O. Smith tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from py_aosmith import AOSmithAPIClient
import pytest

from homeassistant.components.aosmith.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

FIXTURE_USER_INPUT = {
    CONF_EMAIL: "testemail@example.com",
    CONF_PASSWORD: "test-password",
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=FIXTURE_USER_INPUT,
        unique_id=FIXTURE_USER_INPUT[CONF_EMAIL],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aosmith.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def get_devices_fixture() -> str:
    """Return the name of the fixture to use for get_devices."""
    return "get_devices"


@pytest.fixture
async def mock_client(get_devices_fixture: str) -> Generator[MagicMock, None, None]:
    """Return a mocked client."""
    get_devices_fixture = load_json_array_fixture(f"{get_devices_fixture}.json", DOMAIN)
    get_energy_use_fixture = load_json_object_fixture(
        "get_energy_use_data.json", DOMAIN
    )

    client_mock = MagicMock(AOSmithAPIClient)
    client_mock.get_devices = AsyncMock(return_value=get_devices_fixture)
    client_mock.get_energy_use_data = AsyncMock(return_value=get_energy_use_fixture)

    return client_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    with patch(
        "homeassistant.components.aosmith.AOSmithAPIClient", return_value=mock_client
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry
