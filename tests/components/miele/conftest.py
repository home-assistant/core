"""Test helpers for Miele."""

from collections.abc import AsyncGenerator, Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

from pymiele import MieleAction, MieleDevices
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.miele.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import get_actions_callback, get_data_callback
from .const import CLIENT_ID, CLIENT_SECRET

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_value_fixture,
)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, expires_at: float) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        minor_version=1,
        domain=DOMAIN,
        title="Miele test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "Fake_token",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
                "scope": "openid devices basic mcs_thirdparty_read mcs_thirdparty_write mcs_thirdparty_media",
            },
        },
        entry_id="miele_test",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            CLIENT_ID,
            CLIENT_SECRET,
        ),
        DOMAIN,
    )


# Fixture group for device API endpoint.


@pytest.fixture(scope="package")
def load_device_file() -> str:
    """Fixture for loading device file."""
    return "4_devices.json"


@pytest.fixture
async def device_fixture(hass: HomeAssistant, load_device_file: str) -> MieleDevices:
    """Fixture for device."""
    return await async_load_json_object_fixture(hass, load_device_file, DOMAIN)


@pytest.fixture(scope="package")
def load_action_file() -> str:
    """Fixture for loading action file."""
    return "action_washing_machine.json"


@pytest.fixture
async def action_fixture(hass: HomeAssistant, load_action_file: str) -> MieleAction:
    """Fixture for action."""
    return await async_load_json_object_fixture(hass, load_action_file, DOMAIN)


@pytest.fixture(scope="package")
def load_programs_file() -> str:
    """Fixture for loading programs file."""
    return "programs.json"


@pytest.fixture
async def programs_fixture(hass: HomeAssistant, load_programs_file: str) -> list[dict]:
    """Fixture for available programs."""
    return load_json_value_fixture(load_programs_file, DOMAIN)


@pytest.fixture
def mock_miele_client(
    device_fixture,
    action_fixture,
    programs_fixture,
) -> Generator[MagicMock]:
    """Mock a Miele client."""

    with patch(
        "homeassistant.components.miele.MieleAPI",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        client.get_devices.return_value = device_fixture
        client.get_actions.return_value = action_fixture
        client.get_programs.return_value = programs_fixture
        client.set_program.return_value = None

        yield client


@pytest.fixture
def platforms() -> list[str]:
    """Fixture for platforms."""
    return []


@pytest.fixture
async def setup_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platforms,
) -> AsyncGenerator[None]:
    """Set up one or all platforms."""

    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry


@pytest.fixture
async def access_token(hass: HomeAssistant) -> str:
    """Return a valid access token."""
    return "mock-access-token"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.miele.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def push_data_and_actions(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    device_fixture: MieleDevices,
) -> None:
    """Fixture to push data and actions through mock."""

    data_callback = get_data_callback(mock_miele_client)
    await data_callback(device_fixture)
    await hass.async_block_till_done()

    act_file = await async_load_json_object_fixture(hass, "4_actions.json", DOMAIN)
    action_callback = get_actions_callback(mock_miele_client)
    await action_callback(act_file)
    await hass.async_block_till_done()
