"""Define test fixtures for AirVisual Pro."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.airvisual_pro.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="XXXXXXX", data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_IP_ADDRESS: "192.168.1.101",
        CONF_PASSWORD: "password123",
    }


@pytest.fixture(name="connect")
def connect_fixture():
    """Define a mocked async_connect method."""
    return AsyncMock(return_value=True)


@pytest.fixture(name="disconnect")
def disconnect_fixture():
    """Define a mocked async_connect method."""
    return AsyncMock()


@pytest.fixture(name="data", scope="session")
def data_fixture():
    """Define an update coordinator data example."""
    return json.loads(load_fixture("data.json", "airvisual_pro"))


@pytest.fixture(name="pro")
def pro_fixture(connect, data, disconnect):
    """Define a mocked NodeSamba object."""
    return Mock(
        async_connect=connect,
        async_disconnect=disconnect,
        async_get_latest_measurements=AsyncMock(return_value=data),
    )


@pytest.fixture(name="setup_airvisual_pro")
async def setup_airvisual_pro_fixture(hass, config, pro):
    """Define a fixture to set up AirVisual Pro."""
    with patch(
        "homeassistant.components.airvisual_pro.config_flow.NodeSamba", return_value=pro
    ), patch(
        "homeassistant.components.airvisual_pro.NodeSamba", return_value=pro
    ), patch(
        "homeassistant.components.airvisual.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield
