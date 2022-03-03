"""Test the switch light config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.switch.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.helpers import entity_registry as er


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.switch.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_id": "switch.ceiling",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "ceiling"
    assert result["data"] == {}
    assert result["options"] == {"entity_id": "switch.ceiling"}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {"entity_id": "switch.ceiling"}


async def test_name(hass: HomeAssistant) -> None:
    """Test the config flow name is copied from registry entry, with fallback to state."""
    registry = er.async_get(hass)

    # No entry or state, use Object ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling"},
    )
    assert result["title"] == "ceiling"

    # State set, use name from state
    hass.states.async_set("switch.ceiling", "on", {"friendly_name": "State Name"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling"},
    )
    assert result["title"] == "State Name"

    # Entity registered, use original name from registry entry
    hass.states.async_remove("switch.ceiling")
    entry = registry.async_get_or_create(
        "switch",
        "test",
        "unique",
        suggested_object_id="ceiling",
        original_name="Original Name",
    )
    assert entry.entity_id == "switch.ceiling"
    hass.states.async_set("switch.ceiling", "on", {"friendly_name": "State Name"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling"},
    )
    assert result["title"] == "Original Name"

    # Entity has customized name
    registry.async_update_entity("switch.ceiling", name="Custom Name")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling"},
    )
    assert result["title"] == "Custom Name"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]


async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert get_suggested(result["data_schema"].schema, "entity_id") is None
    assert get_suggested(result["data_schema"].schema, "name") is None

    with patch(
        "homeassistant.components.switch.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_id": "switch.ceiling",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "ceiling"
    assert result["data"] == {}
    assert result["options"] == {"entity_id": "switch.ceiling"}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {"entity_id": "switch.ceiling"}

    # Switch light has no options flow
    with pytest.raises(data_entry_flow.UnknownHandler):
        await hass.config_entries.options.async_init(config_entry.entry_id)
