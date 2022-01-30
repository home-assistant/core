"""Define fixtures for Notion tests."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.notion import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="client")
def client_fixture(data_bridge, data_sensor, data_task):
    """Define a fixture for an aionotion client."""
    client = AsyncMock()
    client.bridge.async_all.return_value = data_bridge
    client.sensor.async_all.return_value = data_sensor
    client.task.async_all.return_value = data_task
    return client


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
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }


@pytest.fixture(name="data_bridge", scope="session")
def data_bridge_fixture():
    """Define bridge data."""
    return json.loads(load_fixture("bridge_data.json", "notion"))


@pytest.fixture(name="data_sensor", scope="session")
def data_sensor_fixture():
    """Define sensor data."""
    return json.loads(load_fixture("sensor_data.json", "notion"))


@pytest.fixture(name="data_task", scope="session")
def data_task_fixture():
    """Define task data."""
    return json.loads(load_fixture("task_data.json", "notion"))


@pytest.fixture(name="setup_notion")
async def setup_notion_fixture(hass, client, config):
    """Define a fixture to set up Notion."""
    with patch("homeassistant.components.notion.config_flow.async_get_client"), patch(
        "homeassistant.components.notion.PLATFORMS", []
    ), patch("homeassistant.components.notion.async_get_client", return_value=client):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "user@host.com"
