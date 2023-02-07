"""Provide common test tools."""
from __future__ import annotations

from functools import cache
import json
from typing import Any
from unittest.mock import MagicMock

from matter_server.common.helpers.util import dataclass_from_dict
from matter_server.common.models.events import EventType
from matter_server.common.models.node import MatterNode

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@cache
def load_node_fixture(fixture: str) -> str:
    """Load a fixture."""
    return load_fixture(f"matter/nodes/{fixture}.json")


def load_and_parse_node_fixture(fixture: str) -> dict[str, Any]:
    """Load and parse a node fixture."""
    return json.loads(load_node_fixture(fixture))


async def setup_integration_with_node_fixture(
    hass: HomeAssistant,
    node_fixture: str,
    client: MagicMock,
) -> MatterNode:
    """Set up Matter integration with fixture as node."""
    node_data = load_and_parse_node_fixture(node_fixture)
    node = dataclass_from_dict(
        MatterNode,
        node_data,
    )
    client.get_nodes.return_value = [node]
    client.get_node.return_value = node
    config_entry = MockConfigEntry(
        domain="matter", data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return node


def set_node_attribute(
    node: MatterNode,
    endpoint: int,
    cluster_id: int,
    attribute_id: int,
    value: Any,
) -> None:
    """Set a node attribute."""
    attribute = node.attributes[f"{endpoint}/{cluster_id}/{attribute_id}"]
    attribute.value = value


async def trigger_subscription_callback(
    hass: HomeAssistant,
    client: MagicMock,
    event: EventType = EventType.ATTRIBUTE_UPDATED,
    data: Any = None,
) -> None:
    """Trigger a subscription callback."""
    callback = client.subscribe.call_args[0][0]
    callback(event, data)
    await hass.async_block_till_done()
