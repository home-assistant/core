"""Define test fixtures for IQVIA."""
from unittest.mock import patch

import pytest

from homeassistant.components.iqvia.const import CONF_ZIP_CODE, DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_ZIP_CODE: "12345",
    }


@pytest.fixture(name="setup_iqvia")
async def setup_iqvia_fixture(hass, config):
    """Define a fixture to set up IQVIA."""
    with patch("homeassistant.components.iqvia.PLATFORMS", []):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "12345"
