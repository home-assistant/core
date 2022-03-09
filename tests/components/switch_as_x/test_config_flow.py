"""Test the Switch as X config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.switch_as_x import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize("entity_type", ("light",))
async def test_config_flow(hass: HomeAssistant, entity_type) -> None:
    """Test the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.switch_as_x.async_setup_entry",
        wraps=async_setup_entry,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "entity_id": "switch.ceiling",
                "entity_type": entity_type,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "ceiling"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": "switch.ceiling",
        "entity_type": entity_type,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": "switch.ceiling",
        "entity_type": entity_type,
    }

    assert hass.states.get(f"{entity_type}.ceiling")


@pytest.mark.parametrize("entity_type", ("light",))
async def test_name(hass: HomeAssistant, entity_type) -> None:
    """Test the config flow name is copied from registry entry, with fallback to state."""
    registry = er.async_get(hass)

    # No entry or state, use Object ID
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling", "entity_type": entity_type},
    )
    assert result["title"] == "ceiling"

    # State set, use name from state
    hass.states.async_set("switch.ceiling", "on", {"friendly_name": "State Name"})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling", "entity_type": entity_type},
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
        {"entity_id": "switch.ceiling", "entity_type": entity_type},
    )
    assert result["title"] == "Original Name"

    # Entity has customized name
    registry.async_update_entity("switch.ceiling", name="Custom Name")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"entity_id": "switch.ceiling", "entity_type": entity_type},
    )
    assert result["title"] == "Custom Name"


@pytest.mark.parametrize("entity_type", ("light",))
async def test_options(hass: HomeAssistant, entity_type) -> None:
    """Test reconfiguring."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.switch_as_x.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"entity_id": "switch.ceiling", "entity_type": entity_type},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry

    # Switch light has no options flow
    with pytest.raises(data_entry_flow.UnknownHandler):
        await hass.config_entries.options.async_init(config_entry.entry_id)
