"""Define test fixtures for RainMachine."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.rainmachine import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="client")
def client_fixture(controller_mac):
    """Define a regenmaschine client."""
    controller = AsyncMock()
    controller.name = "My RainMachine"
    controller.mac = controller_mac
    return AsyncMock(load_local=AsyncMock(), controllers={controller_mac: controller})


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, controller_mac):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=controller_mac, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="controller_mac")
def controller_mac_fixture():
    """Define a controller MAC address."""
    return "aa:bb:cc:dd:ee:ff"


@pytest.fixture(name="setup_rainmachine")
async def setup_rainmachine_fixture(hass, client, config):
    """Define a fixture to set up RainMachine."""
    with patch(
        "homeassistant.components.rainmachine.Client", return_value=client
    ), patch(
        "homeassistant.components.rainmachine.config_flow.Client", return_value=client
    ), patch(
        "homeassistant.components.rainmachine.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield
