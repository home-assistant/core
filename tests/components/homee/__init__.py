"""Tests for the homee component."""

from typing import Any
from unittest.mock import AsyncMock

from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.homee.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def build_mock_node(file: str) -> AsyncMock:
    """Build a mocked Homee node from a json representation."""
    json_node = load_json_object_fixture(file, DOMAIN)
    mock_node = AsyncMock(spec=HomeeNode)

    def get_attributes(attributes: list[Any]) -> list[AsyncMock]:
        mock_attributes: list[AsyncMock] = []
        for attribute in attributes:
            att = AsyncMock(spec=HomeeAttribute)
            for key, value in attribute.items():
                setattr(att, key, value)
            att.is_reversed = False
            att.get_value = (
                lambda att=att: att.data if att.unit == "text" else att.current_value
            )
            mock_attributes.append(att)
        return mock_attributes

    for key, value in json_node.items():
        if key != "attributes":
            setattr(mock_node, key, value)

    mock_node.attributes = get_attributes(json_node["attributes"])

    def attribute_by_type(type, instance=0) -> HomeeAttribute | None:
        return {attr.type: attr for attr in mock_node.attributes}.get(type)

    mock_node.get_attribute_by_type = attribute_by_type

    return mock_node


async def async_update_attribute_value(
    hass: HomeAssistant, attribute: AsyncMock, value: float
) -> None:
    """Set the current_value of an attribute and notify hass."""
    attribute.current_value = value
    attribute.add_on_changed_listener.call_args_list[0][0][0](attribute)
    await hass.async_block_till_done()
