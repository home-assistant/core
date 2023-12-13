"""Define test fixtures for IPMA."""

from unittest.mock import patch

import pytest

from homeassistant.components.ipma import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MockLocation

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(domain="ipma", data=ENTRY_CONFIG)


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_NAME: "Home",
        CONF_LATITUDE: 0,
        CONF_LONGITUDE: 0,
    }


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(hass, config_entry):
    """Define a fixture to set up ipma."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def mock_location() -> MockLocation:
    """Define a mock location fixture."""
    return MockLocation()


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_location: MockLocation
) -> MockConfigEntry:
    """Set up the IPMA integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("pyipma.location.Location.get", return_value=mock_location):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry
