"""Test the Universal media player config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.media_player import SERVICE_SELECT_SOURCE
from homeassistant.components.universal import DOMAIN
from homeassistant.components.universal.media_player import (
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    CONF_COMMANDS,
)
from homeassistant.const import (
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

ALL_COMMANDS = (
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    SERVICE_VOLUME_UP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_SELECT_SOURCE,
)


async def test_user_flow_commands(hass: HomeAssistant) -> None:
    """Test the user config flow through to command routing."""
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

    with patch(
        "homeassistant.components.universal.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {SERVICE_TURN_ON: [{"action": "test.turn_on", "data": {}}]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_NAME: "Living room",
        CONF_CHILDREN: ["media_player.mock1", "media_player.mock2"],
        SERVICE_TURN_ON: [{"action": "test.turn_on", "data": {}}],
        SERVICE_TURN_OFF: [],
        SERVICE_VOLUME_UP: [],
        SERVICE_VOLUME_DOWN: [],
        SERVICE_VOLUME_MUTE: [],
        SERVICE_SELECT_SOURCE: [],
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
            **{cmd: [] for cmd in ALL_COMMANDS},
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
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "Living room",
        CONF_CHILDREN: ["media_player.mock2"],
        SERVICE_TURN_ON: [],
        SERVICE_TURN_OFF: [],
        SERVICE_VOLUME_UP: [],
        SERVICE_VOLUME_DOWN: [],
        SERVICE_VOLUME_MUTE: [],
        SERVICE_SELECT_SOURCE: [{"action": "test.select_source"}],
    }
    assert config_entry.options[CONF_CHILDREN] == ["media_player.mock2"]
    assert config_entry.options[SERVICE_SELECT_SOURCE] == [
        {"action": "test.select_source"}
    ]


async def test_import_with_unique_id(hass: HomeAssistant) -> None:
    """Test importing a YAML config that has a unique_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_NAME: "Master bed TV",
            "unique_id": "master_bed_tv",
            CONF_CHILDREN: ["media_player.mock1"],
            CONF_COMMANDS: {
                SERVICE_TURN_ON: {"action": "test.turn_on", "data": {}},
            },
            CONF_ATTRS: {"state": "switch.state"},
            CONF_BROWSE_MEDIA_ENTITY: "media_player.mock1",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Master bed TV"
    assert result["options"] == {
        CONF_NAME: "Master bed TV",
        CONF_CHILDREN: ["media_player.mock1"],
        CONF_ATTRS: {"state": "switch.state"},
        CONF_BROWSE_MEDIA_ENTITY: "media_player.mock1",
        SERVICE_TURN_ON: [{"action": "test.turn_on", "data": {}}],
        SERVICE_TURN_OFF: [],
        SERVICE_VOLUME_UP: [],
        SERVICE_VOLUME_DOWN: [],
        SERVICE_VOLUME_MUTE: [],
        SERVICE_SELECT_SOURCE: [],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.unique_id == "master_bed_tv"


async def test_import_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test importing the same unique_id twice aborts the second time."""
    import_data = {
        CONF_NAME: "Master bed TV",
        "unique_id": "master_bed_tv",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=import_data,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=import_data,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_import_without_unique_id(hass: HomeAssistant) -> None:
    """Test importing a YAML config without a unique_id still creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_NAME: "Kitchen TV"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen TV"

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.unique_id == "yaml_Kitchen TV"
