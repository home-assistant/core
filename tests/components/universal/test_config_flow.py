"""Test the Universal media player config flow."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.media_player import MediaPlayerService
from homeassistant.components.universal import DOMAIN
from homeassistant.components.universal.media_player import (
    CONF_ACTIVE_CHILD_TEMPLATE,
    CONF_ATTRS,
    CONF_BROWSE_MEDIA_ENTITY,
    CONF_CHILDREN,
    EXPOSED_COMMANDS,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_STATE_TEMPLATE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.template import Template


async def test_user_flow_minimal(hass: HomeAssistant) -> None:
    """Test config flow with just a name and children."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.universal.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Living room",
                CONF_CHILDREN: ["media_player.mock1", "media_player.mock2"],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["options"][CONF_NAME] == "Living room"
    assert result["options"][CONF_CHILDREN] == [
        "media_player.mock1",
        "media_player.mock2",
    ]
    assert result["options"][CONF_ATTRS] == {}
    for cmd in EXPOSED_COMMANDS:
        assert result["options"][cmd] == []
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_full(hass: HomeAssistant) -> None:
    """Test config flow with commands, attributes, and advanced fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.universal.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Office Speakers",
                CONF_DEVICE_CLASS: "receiver",
                CONF_STATE_TEMPLATE: "{{ states('input_boolean.office_power') }}",
                MediaPlayerService.SELECT_SOURCE: [
                    {"action": "input_select.select_option"}
                ],
                "source": "input_select.office_inputs",
                "is_volume_muted": "switch.office_mute",
                CONF_CHILDREN: ["media_player.sonos_office"],
                CONF_BROWSE_MEDIA_ENTITY: "media_player.sonos_office",
                CONF_ACTIVE_CHILD_TEMPLATE: "{{ 'media_player.sonos_office' }}",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Office Speakers"
    opts = result["options"]
    assert opts[CONF_DEVICE_CLASS] == "receiver"
    assert opts[CONF_STATE_TEMPLATE] == "{{ states('input_boolean.office_power') }}"
    assert opts[MediaPlayerService.SELECT_SOURCE] == [
        {"action": "input_select.select_option"}
    ]
    assert opts[CONF_ATTRS] == {
        "source": "input_select.office_inputs",
        "is_volume_muted": "switch.office_mute",
    }
    assert opts[CONF_CHILDREN] == ["media_player.sonos_office"]
    assert opts[CONF_BROWSE_MEDIA_ENTITY] == "media_player.sonos_office"
    assert opts[CONF_ACTIVE_CHILD_TEMPLATE] == "{{ 'media_player.sonos_office' }}"


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [["component.media_player.services."]],
)
async def test_options_flow(hass: HomeAssistant) -> None:
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
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CHILDREN: ["media_player.mock2"],
            CONF_DEVICE_CLASS: "speaker",
            MediaPlayerService.SELECT_SOURCE: [{"action": "test.select_source"}],
            "source": "input_select.living_room_source",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_CHILDREN] == ["media_player.mock2"]
    assert config_entry.options[CONF_DEVICE_CLASS] == "speaker"
    assert config_entry.options[CONF_ATTRS] == {
        "source": "input_select.living_room_source"
    }
    assert config_entry.options[MediaPlayerService.SELECT_SOURCE] == [
        {"action": "test.select_source"}
    ]


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [["component.media_player.services."]],
)
async def test_options_flow_suggested_values(hass: HomeAssistant) -> None:
    """Test that options flow pre-populates with current values."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        options={
            CONF_NAME: "Test",
            CONF_CHILDREN: ["media_player.child1"],
            CONF_DEVICE_CLASS: "tv",
            CONF_ATTRS: {"source": "input_select.tv_source"},
            CONF_STATE_TEMPLATE: "{{ states('switch.tv') }}",
            **{cmd: [] for cmd in EXPOSED_COMMANDS},
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_import_yaml(hass: HomeAssistant) -> None:
    """Test importing a YAML config into a config entry."""
    yaml_config = {
        CONF_NAME: "Office Speakers",
        CONF_CHILDREN: ["media_player.sonos"],
        CONF_DEVICE_CLASS: "receiver",
        CONF_STATE_TEMPLATE: Template("{{ states('input_boolean.power') }}", hass),
        "commands": {
            MediaPlayerService.TURN_ON: {
                "service": "input_boolean.turn_on",
                "data_template": {"entity_id": "input_boolean.power"},
            },
            MediaPlayerService.SELECT_SOURCE: {
                "service": "input_select.select_option",
                "data_template": {"entity_id": "input_select.inputs"},
            },
        },
        CONF_ATTRS: {
            "source": "input_select.inputs",
            "is_volume_muted": "switch.mute",
        },
    }

    with patch(
        "homeassistant.components.universal.async_setup_entry",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=yaml_config
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    opts = result["options"]
    assert opts[CONF_NAME] == "Office Speakers"
    assert opts[CONF_CHILDREN] == ["media_player.sonos"]
    assert opts[CONF_DEVICE_CLASS] == "receiver"
    assert opts[CONF_STATE_TEMPLATE] == "{{ states('input_boolean.power') }}"

    # service -> action, data_template -> data, entity_id moved to target
    turn_on = opts[MediaPlayerService.TURN_ON]
    assert len(turn_on) == 1
    assert turn_on[0]["action"] == "input_boolean.turn_on"
    assert "service" not in turn_on[0]
    assert turn_on[0]["target"]["entity_id"] == "input_boolean.power"

    assert opts[CONF_ATTRS] == {
        "source": "input_select.inputs",
        "is_volume_muted": "switch.mute",
    }


async def test_import_yaml_dedup(hass: HomeAssistant) -> None:
    """Test that importing the same YAML config twice is deduplicated."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Office Speakers",
        options={
            CONF_NAME: "Office Speakers",
            CONF_CHILDREN: [],
            CONF_ATTRS: {},
            **{cmd: [] for cmd in EXPOSED_COMMANDS},
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_NAME: "Office Speakers"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_yaml_dedup_unique_id(hass: HomeAssistant) -> None:
    """Test that YAML import deduplicates by unique_id when present."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Office Speakers",
        unique_id="my_unique_player",
        options={
            CONF_NAME: "Office Speakers",
            CONF_CHILDREN: [],
            CONF_ATTRS: {},
            CONF_UNIQUE_ID: "my_unique_player",
            **{cmd: [] for cmd in EXPOSED_COMMANDS},
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_NAME: "Different Name", CONF_UNIQUE_ID: "my_unique_player"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
