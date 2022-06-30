"""Define test fixtures for Ambient PWS."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.ambient_station.const import CONF_APP_KEY, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: "12345abcde12345abcde",
        CONF_APP_KEY: "67890fghij67890fghij",
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="devices", scope="session")
def devices_fixture():
    """Define devices data."""
    return json.loads(load_fixture("devices.json", "ambient_station"))


@pytest.fixture(name="setup_ambient_station")
async def setup_ambient_station_fixture(hass, config, devices):
    """Define a fixture to set up AirVisual."""
    with patch("homeassistant.components.ambient_station.PLATFORMS", []), patch(
        "homeassistant.components.ambient_station.config_flow.API.get_devices",
        side_effect=devices,
    ), patch("aioambient.api.API.get_devices", side_effect=devices), patch(
        "aioambient.websocket.Websocket.connect"
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="station_data", scope="session")
def station_data_fixture():
    """Define devices data."""
    return json.loads(load_fixture("station_data.json", "ambient_station"))
