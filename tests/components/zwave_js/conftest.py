"""Provide common Z-Wave JS fixtures."""
import json
from unittest.mock import patch

import pytest
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="controller_state", scope="session")
def controller_state_fixture():
    """Load the controller state fixture data."""
    return json.loads(load_fixture("zwave_js/controller_state.json"))


@pytest.fixture(name="multisensor_6_state", scope="session")
def multisensor_6_state_fixture():
    """Load the multisensor 6 node state fixture data."""
    return json.loads(load_fixture("zwave_js/multisensor_6_state.json"))


@pytest.fixture(name="client")
def mock_client_fixture(controller_state):
    """Mock a client."""
    with patch(
        "homeassistant.components.zwave_js.ZwaveClient", autospec=True
    ) as client_class:
        driver = Driver(client_class.return_value, controller_state)
        client_class.return_value.driver = driver
        yield client_class.return_value


@pytest.fixture(name="multisensor_6")
def multisensor_6_fixture(client, multisensor_6_state):
    """Mock a multisensor 6 node."""
    node = Node(client, multisensor_6_state)
    client.driver.controller.nodes[node.node_id] = node
    return node


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
