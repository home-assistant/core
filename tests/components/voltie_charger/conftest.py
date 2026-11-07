"""Fixtures for the Voltie Charger integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from voltie import Status
from yarl import URL

from homeassistant.components.voltie_charger.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

CHARGER_ID = "000000009d104335"
HOST = "192.168.1.234"
PORT = 5059


def status_fixture(**overrides: object) -> Status:
    """Return a parsed status, with fields of the fixture replaced."""
    return Status.from_dict(
        {**load_json_object_fixture("status.json", DOMAIN), **overrides}
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Voltie Charger 4335",
        domain=DOMAIN,
        version=2,
        data={CONF_HOST: HOST, CONF_PORT: PORT},
        unique_id=CHARGER_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.voltie_charger.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def api_version() -> int | None:
    """Return the HTTP API version the mocked charger reports."""
    return 5


@pytest.fixture
def mock_voltie_class(api_version: int | None) -> Generator[MagicMock]:
    """Return the mocked Voltie charger client class."""
    with (
        patch(
            "homeassistant.components.voltie_charger.VoltieCharger", autospec=True
        ) as voltie_mock,
        patch(
            "homeassistant.components.voltie_charger.config_flow.VoltieCharger",
            new=voltie_mock,
        ),
    ):
        charger = voltie_mock.return_value
        charger.host = HOST
        charger.port = PORT
        charger.url = URL.build(scheme="http", host=HOST, port=PORT)
        charger.status.return_value = status_fixture()
        charger.api_version.return_value = api_version
        yield voltie_mock


@pytest.fixture
def mock_voltie(mock_voltie_class: MagicMock) -> MagicMock:
    """Return a mocked Voltie charger client."""
    return mock_voltie_class.return_value


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_voltie: MagicMock,
) -> MockConfigEntry:
    """Set up the Voltie Charger integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
