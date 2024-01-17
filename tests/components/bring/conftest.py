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


@pytest.fixture
def mock_setup_entry() -> Generator[Mock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bring.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="bring_config_entry")
def mock_bring_config_entry() -> MockConfigEntry:
    """Mock bring configuration."""
    return MockConfigEntry(
        domain=DOMAIN, data={CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}
    )


@pytest.fixture(name="bring")
def mock_bring() -> Mock:
    """Mock the Bring api."""
    b = Mock()
    b.login.return_value = True
    b.loadLists.return_value = {"lists": []}
    return b


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    bring: Mock,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the bring integration."""
    bring_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.bring.Bring", return_value=bring):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield
