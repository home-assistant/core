"""Common fixtures for the Bring! tests."""
from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.bring import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

EMAIL = "test-email"
PASSWORD = "test-password"

UUID = "00000000-00000000-00000000-00000000"


@pytest.fixture
def mock_setup_entry() -> Generator[Mock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bring.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_bring_client() -> Generator[Mock, None, None]:
    """Mock a Bring client."""
    with patch(
        "homeassistant.components.bring.Bring",
        autospec=True,
    ) as mock_client, patch(
        "homeassistant.components.bring.config_flow.Bring",
        new=mock_client,
    ):
        client = mock_client.return_value
        client.uuid = UUID
        client.login.return_value = True
        client.loadLists.return_value = {"lists": []}
        yield client


@pytest.fixture(name="bring_config_entry")
def mock_bring_config_entry() -> MockConfigEntry:
    """Mock bring configuration."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    mock_bring_client: Mock,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the bring integration."""
    bring_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture
def login_with_error(exception, mock_bring_client: Mock):
    """Fixture to simulate error on login."""
    mock_bring_client.login.side_effect = (exception,)
