"""Define fixtures for AirNow tests."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.airnow import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{config[CONF_LATITUDE]}-{config[CONF_LONGITUDE]}",
        data=config,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: "abc123",
        CONF_LATITUDE: 34.053718,
        CONF_LONGITUDE: -118.244842,
        CONF_RADIUS: 75,
    }


@pytest.fixture(name="response", scope="session")
def response_fixture():
    """Define task data."""
    return json.loads(load_fixture("response.json", "airnow"))


@pytest.fixture(name="setup_airnow")
async def setup_airnow_fixture(hass, config):
    """Define a fixture to set up AirNow."""
    with patch("pyairnow.WebServiceAPI._get", return_value=config), patch(
        "homeassistant.components.airnow.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield
