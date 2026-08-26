"""Fixtures for the NexBlue integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from nexblue_api import Charger, ChargerStatus, TokenBundle
import pytest

from homeassistant.components.nexblue.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

CHARGER = Charger.from_api(load_json_object_fixture("charger.json", DOMAIN))
CHARGER_STATUS = ChargerStatus.from_api(
    CHARGER.serial_number, load_json_object_fixture("charger_status.json", DOMAIN)
)
TOKEN = TokenBundle.from_api(load_json_object_fixture("token.json", DOMAIN))


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a NexBlue config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NexBlue (user@example.com)",
        unique_id=TOKEN.account_id,
        data={
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "password",
            CONF_REFRESH_TOKEN: TOKEN.refresh_token,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Prevent a config-flow test from setting up the integration."""
    with patch("homeassistant.components.nexblue.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mocked NexBlue API client."""
    with (
        patch(
            "homeassistant.components.nexblue.NexBlueClient", autospec=True
        ) as client_mock,
        patch(
            "homeassistant.components.nexblue.config_flow.NexBlueClient",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.async_login.return_value = TOKEN
        client.async_ensure_access_token.return_value = None
        client.async_list_chargers.return_value = [CHARGER]
        client.async_get_charger_status.return_value = CHARGER_STATUS
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the NexBlue integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
