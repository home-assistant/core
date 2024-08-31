"""Define test fixtures for IPMA."""

import pytest

from homeassistant.components.ipma import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.common import MockConfigEntry


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
