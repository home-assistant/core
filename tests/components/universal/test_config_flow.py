"""Test the Universal media player config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.media_player import SERVICE_SELECT_SOURCE
from homeassistant.components.universal import DOMAIN
from homeassistant.components.universal.media_player import (
    CONF_ACTIVE_CHILD_TEMPLATE,
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    CONF_COMMANDS,
    EXPOSED_COMMANDS,
    PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_STATE_TEMPLATE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.json import json_bytes_sorted

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
            CONF_ATTRS: {"state": "switch.old_state", "legacy_attr": "sensor.legacy"},
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

    # Clearing "state" (leaving it blank) should remove the override, while
    # the "legacy_attr" key (not exposed in the UI) should be preserved.
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
        CONF_ATTRS: {
            "source": "input_select.living_room_source",
            "legacy_attr": "sensor.legacy",
        },
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
        "source": "input_select.living_room_source",
        "legacy_attr": "sensor.legacy",
    }
    assert config_entry.options[SERVICE_SELECT_SOURCE] == [
        {"action": "test.select_source"}
    ]


async def test_import_with_unique_id(hass: HomeAssistant) -> None:
    """Test importing a YAML config that has a unique_id.

    The raw config is run through PLATFORM_SCHEMA first, like a real YAML
    config would be, so device_class and the templates arrive as the coerced
    types (a MediaPlayerDeviceClass StrEnum and Template objects) rather than
    plain strings; this is what previously caused the config entry storage
    write to fail (StrEnum members are not accepted by the JSON encoder).
    """
    raw_config = PLATFORM_SCHEMA(
        {
            "platform": "universal",
            CONF_NAME: "Master bed TV",
            "unique_id": "master_bed_tv",
            CONF_CHILDREN: ["media_player.mock1"],
            CONF_COMMANDS: {
                "turn_on": {
                    "action": "test.turn_on",
                    "data": {"level": "{{ volume_level }}"},
                },
                "play_media": {"action": "test.play_media"},
            },
            CONF_ATTRS: {"state": "switch.state"},
            CONF_BROWSE_MEDIA_ENTITY: "media_player.mock1",
            CONF_DEVICE_CLASS: "tv",
            CONF_ACTIVE_CHILD_TEMPLATE: "{{ 'media_player.mock1' }}",
            CONF_STATE_TEMPLATE: "{{ states('media_player.mock1') }}",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=raw_config,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Master bed TV"
    assert result["options"] == {
        CONF_NAME: "Master bed TV",
        CONF_CHILDREN: ["media_player.mock1"],
        CONF_ATTRS: {"state": "switch.state"},
        CONF_BROWSE_MEDIA_ENTITY: "media_player.mock1",
        CONF_DEVICE_CLASS: "tv",
        CONF_ACTIVE_CHILD_TEMPLATE: "{{ 'media_player.mock1' }}",
        CONF_STATE_TEMPLATE: "{{ states('media_player.mock1') }}",
        # play_media isn't in EXPOSED_COMMANDS (no UI field for it), so it's
        # preserved separately rather than dropped.
        CONF_COMMANDS: {"play_media": {"action": "test.play_media"}},
        **{
            cmd: [{"action": "test.turn_on", "data": {"level": "{{ volume_level }}"}}]
            if cmd == "turn_on"
            else []
            for cmd in EXPOSED_COMMANDS
        },
    }
    # Dict equality alone doesn't catch a StrEnum smuggled in for
    # device_class, since MediaPlayerDeviceClass.TV == "tv"; config entry
    # options must be plain, JSON-serialisable types. Likewise, CMD_SCHEMA
    # compiles a templated command "data" value into a Template object, which
    # must be flattened back to its raw text for the same reason.
    assert type(result["options"][CONF_DEVICE_CLASS]) is str
    assert type(result["options"][CONF_ACTIVE_CHILD_TEMPLATE]) is str
    assert type(result["options"][CONF_STATE_TEMPLATE]) is str
    assert type(result["options"]["turn_on"][0]["data"]["level"]) is str
    json_bytes_sorted(hass.config_entries.async_entries(DOMAIN)[0].as_dict())

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
