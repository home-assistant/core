"""Define test fixtures for OpenUV."""
from unittest.mock import patch

import pytest

from homeassistant.components.openuv import CONF_FROM_WINDOW, CONF_TO_WINDOW, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data=config,
        options={CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 3.5},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: "abcde12345",
        CONF_ELEVATION: 0,
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }


@pytest.fixture(name="setup_openuv")
async def setup_openuv_fixture(hass, config):
    """Define a fixture to set up OpenUV."""
    with patch("homeassistant.components.openuv.Client.uv_index"), patch(
        "homeassistant.components.openuv.Client.uv_protection_window"
    ), patch("homeassistant.components.openuv.PLATFORMS", []):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "51.528308, -0.3817765"
