"""Provide common test tools."""
from __future__ import annotations

import asyncio
from functools import cache
import json
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, patch

from matter_server.client.client import Client
from matter_server.client.model.driver import Driver
from matter_server.client.model.node import MatterNode
from matter_server.common import json_utils
from matter_server.common.model.message import ServerInformation
from matter_server.vendor.chip.clusters.ObjectsVersion import CLUSTER_OBJECT_VERSION
import pytest

from tests.common import MockConfigEntry, load_fixture

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

MOCK_FABRIC_ID = 12341234
MOCK_COMPR_FABRIC_ID = 1234


class MockClient(Client):
    """Represent a mock Matter client."""

    mock_client_disconnect: asyncio.Event
    mock_commands: dict[type, Any] = {}
    mock_sent_commands: list[dict[str, Any]] = []

    def __init__(self) -> None:
        """Initialize the mock client."""
        super().__init__("mock-url", None)
        self.mock_commands: dict[type, Any] = {}
        self.mock_sent_commands = []
        self.server_info = ServerInformation(
            fabricId=MOCK_FABRIC_ID, compressedFabricId=MOCK_COMPR_FABRIC_ID
        )

    async def connect(self) -> None:
        """Connect to the Matter server."""
        self.server_info = Mock(compressedFabricId=MOCK_COMPR_FABRIC_ID)

    async def listen(self, driver_ready: asyncio.Event) -> None:
        """Listen for events."""
        self.driver = Driver(self)
        driver_ready.set()
        self.mock_client_disconnect = asyncio.Event()
        await self.mock_client_disconnect.wait()

    def mock_command(self, command_type: type, response: Any) -> None:
        """Mock a command."""
        self.mock_commands[command_type] = response

    async def async_send_command(
        self,
        command: str,
        args: dict[str, Any],
        require_schema: int | None = None,
    ) -> dict:
        """Send mock commands."""
        if command == "device_controller.SendCommand" and (
            (cmd_type := type(args.get("payload"))) in self.mock_commands
        ):
            self.mock_sent_commands.append(args)
            return self.mock_commands[cmd_type]

        return await super().async_send_command(command, args, require_schema)

    async def async_send_command_no_wait(
        self, command: str, args: dict[str, Any], require_schema: int | None = None
    ) -> None:
        """Send a command without waiting for the response."""
        if command == "SendCommand" and (
            (cmd_type := type(args.get("payload"))) in self.mock_commands
        ):
            self.mock_sent_commands.append(args)
            return self.mock_commands[cmd_type]

        return await super().async_send_command_no_wait(command, args, require_schema)


@pytest.fixture
async def mock_matter() -> Mock:
    """Mock matter fixture."""
    return await get_mock_matter()


async def get_mock_matter() -> Mock:
    """Get mock Matter."""
    return Mock(
        adapter=Mock(logger=logging.getLogger("mock_matter")), client=MockClient()
    )


@cache
def load_node_fixture(fixture: str) -> str:
    """Load a fixture."""
    return load_fixture(f"matter/nodes/{fixture}.json")


def load_and_parse_node_fixture(fixture: str) -> dict[str, Any]:
    """Load and parse a node fixture."""
    return json.loads(load_node_fixture(fixture), cls=json_utils.CHIPJSONDecoder)


async def setup_integration_with_node_fixture(
    hass: HomeAssistant, hass_storage: dict[str, Any], node_fixture: str
) -> MatterNode:
    """Set up Matter integration with fixture as node."""
    node_data = load_and_parse_node_fixture(node_fixture)
    node = MatterNode(
        await get_mock_matter(),
        node_data,
    )
    config_entry = MockConfigEntry(
        domain="matter", data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)

    storage_key = f"matter_{config_entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 0,
        "key": storage_key,
        "data": {
            "compressed_fabric_id": MOCK_COMPR_FABRIC_ID,
            "next_node_id": 4339,
            "node_interview_version": CLUSTER_OBJECT_VERSION,
            "nodes": {str(node.node_id): node_data},
        },
    }

    with patch(
        "matter_server.client.matter.Client", return_value=node.matter.client
    ), patch(
        "matter_server.client.model.node.MatterDeviceTypeInstance.subscribe_updates",
    ), patch(
        "matter_server.client.model.node.MatterDeviceTypeInstance.update_attributes"
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return node
