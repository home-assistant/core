"""Provide common Z-Wave JS fixtures."""
import json
from unittest.mock import patch

import pytest
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="basic_data", scope="session")
def basic_data_fixture():
    """Load the basic fixture data."""
    return load_fixture("zwave_js/basic_dump.txt").split("\n")


@pytest.fixture(name="client")
def mock_client_fixture(basic_data):
    """Mock a client."""
    state = json.loads(basic_data[0])["state"]
    state["nodes"].clear()
    with patch(
        "homeassistant.components.zwave_js.ZwaveClient", autospec=True
    ) as client_class:
        driver = Driver(state)
        client_class.return_value.driver = driver
        yield client_class.return_value


@pytest.fixture(name="multisensor_6")
def multisensor_6_fixture(basic_data, client):
    """Mock a multisensor 6 node."""
    state = json.loads(basic_data[0])["state"]
    for node_data in state["nodes"]:
        if node_data["nodeId"] == 52:
            node = Node(node_data)
            client.driver.controller.nodes = {node.node_id: node}
            return node

    raise RuntimeError("Bad fixture data")


@pytest.fixture(name="integration")
async def integration_fixture(hass, client):
    """Set up the zwave_js integration."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    def initialize_client(async_on_initialized):
        """Init the client."""
        hass.async_create_task(async_on_initialized())

    client.register_on_initialized.side_effect = initialize_client

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
