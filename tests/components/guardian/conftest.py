"""Define fixtures for Elexa Guardian tests."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.guardian.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PORT: 7777,
    }


@pytest.fixture(name="data_ping", scope="session")
def data_ping_fixture():
    """Define data from a successful ping response."""
    return json.loads(load_fixture("ping_data.json", "guardian"))


@pytest.fixture(name="setup_guardian")
async def setup_guardian_fixture(hass, config, data_ping):
    """Define a fixture to set up Guardian."""
    with patch("aioguardian.client.Client.connect"), patch(
        "aioguardian.commands.system.SystemCommands.ping",
        return_value=data_ping,
    ), patch("aioguardian.client.Client.disconnect"), patch(
        "homeassistant.components.guardian.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "guardian_3456"
