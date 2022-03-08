"""Test the Switch config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.group import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


@pytest.mark.parametrize(
    "group_type,group_state,member_state,member_attributes",
    (
        ("cover", "open", "open", {}),
        ("fan", "on", "on", {}),
        ("light", "on", "on", {}),
        ("media_player", "on", "on", {}),
    ),
)
async def test_config_flow(
    hass: HomeAssistant, group_type, group_state, member_state, member_attributes
) -> None:
    """Test the config flow."""
    members = [f"{group_type}.one", f"{group_type}.two"]
    for member in members:
        hass.states.async_set(member, member_state, member_attributes)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"group_type": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == group_type

    with patch(
        "homeassistant.components.group.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Living Room",
                "entities": members,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"] == {}
    assert result["options"] == {
        "group_type": group_type,
        "entities": members,
        "name": "Living Room",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "group_type": group_type,
        "name": "Living Room",
        "entities": members,
    }

    state = hass.states.get(f"{group_type}.living_room")
    assert state.state == group_state
    assert state.attributes["entity_id"] == members


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize(
    "group_type,member_state",
    (("cover", "open"), ("fan", "on"), ("light", "on"), ("media_player", "on")),
)
async def test_options(hass: HomeAssistant, group_type, member_state) -> None:
    """Test reconfiguring."""
    members1 = [f"{group_type}.one", f"{group_type}.two"]
    members2 = [f"{group_type}.four", f"{group_type}.five"]

    for member in members1:
        hass.states.async_set(member, member_state, {})
    for member in members2:
        hass.states.async_set(member, member_state, {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    assert get_suggested(result["data_schema"].schema, "group_type") is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"group_type": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == group_type

    assert get_suggested(result["data_schema"].schema, "entities") is None
    assert get_suggested(result["data_schema"].schema, "name") is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Bed Room",
            "entities": members1,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    state = hass.states.get(f"{group_type}.bed_room")
    assert state.attributes["entity_id"] == members1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "group_type": group_type,
        "entities": members1,
        "name": "Bed Room",
    }

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == f"{group_type}_options"
    assert get_suggested(result["data_schema"].schema, "entities") == members1
    assert "name" not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entities": members2,
        },
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "group_type": group_type,
        "entities": members2,
        "name": "Bed Room",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "group_type": group_type,
        "entities": members2,
        "name": "Bed Room",
    }
    assert config_entry.title == "Bed Room"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    state = hass.states.get(f"{group_type}.bed_room")
    assert state.attributes["entity_id"] == members2

    # Check we don't get suggestions from another entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None
    assert get_suggested(result["data_schema"].schema, "group_type") is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"group_type": group_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == group_type

    assert get_suggested(result["data_schema"].schema, "entities") is None
    assert get_suggested(result["data_schema"].schema, "name") is None
