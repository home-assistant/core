"""Test the Universal media player config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.media_player import SERVICE_SELECT_SOURCE
from homeassistant.components.universal import DOMAIN
from homeassistant.components.universal.media_player import (
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    EXPOSED_COMMANDS,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_commands(hass: HomeAssistant) -> None:
    """Test the user config flow through to command routing, attributes and advanced."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Living room",
            CONF_CHILDREN: ["media_player.mock1", "media_player.mock2"],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "commands"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SERVICE_SELECT_SOURCE: [{"action": "test.select_source"}]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "attributes"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"state": "switch.living_room_tv"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "advanced"

    with patch(
        "homeassistant.components.universal.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_CLASS: "tv",
                CONF_BROWSE_MEDIA_ENTITY: "media_player.mock2",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_NAME: "Living room",
        CONF_CHILDREN: ["media_player.mock1", "media_player.mock2"],
        CONF_ATTRS: {"state": "switch.living_room_tv"},
        CONF_DEVICE_CLASS: "tv",
        CONF_BROWSE_MEDIA_ENTITY: "media_player.mock2",
        **{
            cmd: [{"action": "test.select_source"}]
            if cmd == SERVICE_SELECT_SOURCE
            else []
            for cmd in EXPOSED_COMMANDS
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.title == "Living room"
    assert config_entry.options[CONF_CHILDREN] == [
        "media_player.mock1",
        "media_player.mock2",
    ]


async def test_options_flow_edit(hass: HomeAssistant) -> None:
    """Test editing an existing entry through the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        options={
            CONF_NAME: "Living room",
            CONF_CHILDREN: ["media_player.mock1"],
            CONF_ATTRS: {"state": "switch.old_state"},
            **{cmd: [] for cmd in EXPOSED_COMMANDS},
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_CHILDREN: ["media_player.mock2"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "commands"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={SERVICE_SELECT_SOURCE: [{"action": "test.select_source"}]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "attributes"

    # Clearing "state" (leaving it blank) should remove the override.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"source": "input_select.living_room_source"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "advanced"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_CLASS: "speaker"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "Living room",
        CONF_CHILDREN: ["media_player.mock2"],
        CONF_ATTRS: {"source": "input_select.living_room_source"},
        CONF_DEVICE_CLASS: "speaker",
        **{
            cmd: [{"action": "test.select_source"}]
            if cmd == SERVICE_SELECT_SOURCE
            else []
            for cmd in EXPOSED_COMMANDS
        },
    }
    assert config_entry.options[CONF_CHILDREN] == ["media_player.mock2"]
    assert config_entry.options[CONF_ATTRS] == {
        "source": "input_select.living_room_source"
    }
    assert config_entry.options[SERVICE_SELECT_SOURCE] == [
        {"action": "test.select_source"}
    ]
