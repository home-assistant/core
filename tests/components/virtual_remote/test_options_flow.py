"""Tests for the Virtual Remote options flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.components.virtual_remote.options_flow import (
    COMMAND_DATA,
    COMMAND_NAME,
    SOURCE_ADD_COMMAND,
    SOURCE_EDIT_COMMAND,
    SOURCE_EDIT_REMOTE,
    SOURCE_MANAGE_COMMANDS,
    SOURCE_REMOVE_COMMAND,
    VirtualRemoteOptionsFlow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import INFRARED_ENTITY_ID, RAW_COMMAND

from tests.common import MockConfigEntry


async def _init_options_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    source: str | None = None,
):
    """Initialize the options flow."""
    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={
            "source": "init",
            "entry_id": entry.entry_id,
        },
    )
    if source is None:
        return result

    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": source},
    )


def _single_entry(hass: HomeAssistant, infrared_entity: str) -> MockConfigEntry:
    """Create a one-remote config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room TV",
        data={
            CONF_REMOTE_ID: "living_room_tv",
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: infrared_entity,
        },
        options={CONF_REMOTE_COMMANDS: {"POWER_ON": RAW_COMMAND}},
        unique_id="living_room_tv",
    )
    entry.add_to_hass(hass)
    return entry


def _single_entry_without_commands(
    hass: HomeAssistant, infrared_entity: str
) -> MockConfigEntry:
    """Create a one-remote config entry without commands."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room TV",
        data={
            CONF_REMOTE_ID: "living_room_tv",
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: infrared_entity,
        },
        options={},
        unique_id="living_room_tv",
    )
    entry.add_to_hass(hass)
    return entry


async def test_options_menu(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test options menu for a single remote entry."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry)

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [SOURCE_EDIT_REMOTE, SOURCE_MANAGE_COMMANDS]


async def test_options_menu_without_remote_aborts(hass: HomeAssistant) -> None:
    """Test options flow aborts when the config entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    result = await _init_options_flow(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_edit_remote_success_single_entry(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test editing the current remote stores overrides in options."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_EDIT_REMOTE)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_EDIT_REMOTE

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_REMOTE_NAME: "Updated TV",
            CONF_INFRARED_ENTITY_ID: infrared_entity,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_REMOTE_NAME not in result["data"]
    assert CONF_INFRARED_ENTITY_ID not in result["data"]
    assert entry.data[CONF_REMOTE_NAME] == "Updated TV"
    assert entry.data[CONF_INFRARED_ENTITY_ID] == infrared_entity


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {CONF_REMOTE_NAME: "", CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID},
            {CONF_REMOTE_NAME: "remote_name_required"},
        ),
    ],
)
async def test_edit_remote_errors(
    hass: HomeAssistant,
    infrared_entity: str,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test editing the current remote validation errors."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_EDIT_REMOTE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_edit_remote_no_infrared_entities(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test editing aborts when no infrared entities are available."""
    entry = _single_entry(hass, infrared_entity)

    with patch(
        "homeassistant.components.virtual_remote.options_flow.available_infrared_entities",
        return_value={},
    ):
        result = await _init_options_flow(hass, entry, SOURCE_EDIT_REMOTE)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_manage_commands_menu_with_commands(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test manage commands menu includes edit/remove when commands exist."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == SOURCE_MANAGE_COMMANDS
    assert result["menu_options"] == [
        SOURCE_ADD_COMMAND,
        SOURCE_EDIT_COMMAND,
        SOURCE_REMOVE_COMMAND,
    ]


async def test_manage_commands_menu_without_commands(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test manage commands menu only includes add when no commands exist."""
    entry = _single_entry_without_commands(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [SOURCE_ADD_COMMAND]


async def test_manage_commands_without_remote_aborts(hass: HomeAssistant) -> None:
    """Test manage commands aborts when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_manage_commands()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_add_command_success(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test adding a command."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_ADD_COMMAND},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_ADD_COMMAND

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "HDMI 1", COMMAND_DATA: RAW_COMMAND},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REMOTE_COMMANDS]["HDMI_1"] == RAW_COMMAND


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {COMMAND_NAME: "", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_required"},
        ),
        (
            {COMMAND_NAME: "Power On", COMMAND_DATA: ""},
            {COMMAND_DATA: "command_data_required"},
        ),
        (
            {COMMAND_NAME: "Power On", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_exists"},
        ),
        (
            {COMMAND_NAME: "HDMI", COMMAND_DATA: "bad"},
            {COMMAND_DATA: "invalid_command"},
        ),
    ],
)
async def test_add_command_errors(
    hass: HomeAssistant,
    infrared_entity: str,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test adding command validation errors."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_add_command_without_remote_aborts(hass: HomeAssistant) -> None:
    """Test add command aborts when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_add_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_select_command_for_edit_form(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test selecting a command for edit."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_EDIT_COMMAND},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_command_for_edit"


async def test_select_command_for_edit_without_commands_aborts(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test selecting command for edit aborts without commands."""
    entry = _single_entry_without_commands(hass, infrared_entity)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_select_command_for_edit()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remote_commands"


async def test_edit_command_success(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test editing a command."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "POWER_ON"},
    )
    assert result["step_id"] == "edit_command"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "HDMI 1", COMMAND_DATA: RAW_COMMAND},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "POWER_ON" not in result["data"][CONF_REMOTE_COMMANDS]
    assert result["data"][CONF_REMOTE_COMMANDS]["HDMI_1"] == RAW_COMMAND


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {COMMAND_NAME: "", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_required"},
        ),
        (
            {COMMAND_NAME: "Power", COMMAND_DATA: ""},
            {COMMAND_DATA: "command_data_required"},
        ),
        (
            {COMMAND_NAME: "Power", COMMAND_DATA: "bad"},
            {COMMAND_DATA: "invalid_command"},
        ),
    ],
)
async def test_edit_command_errors(
    hass: HomeAssistant,
    infrared_entity: str,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test editing command validation errors."""
    entry = _single_entry(hass, infrared_entity)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass
    flow._selected_command_name = "POWER_ON"

    result = await flow.async_step_edit_command(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_edit_command_duplicate_name(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test editing command rejects another existing command name."""
    entry = _single_entry(hass, infrared_entity)
    entry.options[CONF_REMOTE_COMMANDS]["POWER_OFF"] = RAW_COMMAND

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass
    flow._selected_command_name = "POWER_ON"

    result = await flow.async_step_edit_command(
        {COMMAND_NAME: "POWER_OFF", COMMAND_DATA: RAW_COMMAND}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {COMMAND_NAME: "command_name_exists"}


async def test_edit_command_missing_selection_shows_select_form(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test edit command redirects to selection form when no command is selected."""
    entry = _single_entry(hass, infrared_entity)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_edit_command()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_command_for_edit"


async def test_edit_command_missing_selection_submit_aborts(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test edit command aborts when submitted selected command is gone."""
    entry = _single_entry(hass, infrared_entity)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass
    flow._selected_command_name = "MISSING"

    result = await flow.async_step_edit_command(
        {COMMAND_NAME: "HDMI", COMMAND_DATA: RAW_COMMAND}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "command_not_found"


async def test_edit_command_without_remote_or_commands_aborts(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test edit command abort conditions."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_edit_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"

    entry = _single_entry_without_commands(hass, infrared_entity)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_edit_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remote_commands"


async def test_remove_command_success(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test removing a command."""
    entry = _single_entry(hass, infrared_entity)

    result = await _init_options_flow(hass, entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_REMOVE_COMMAND},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_REMOVE_COMMAND

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "POWER_ON"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_REMOTE_COMMANDS not in result["data"]


async def test_remove_command_without_commands_aborts(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test removing command aborts without commands."""
    entry = _single_entry_without_commands(hass, infrared_entity)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_remove_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remote_commands"


async def test_remove_command_missing_command_aborts(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test removing stale command aborts."""
    entry = _single_entry(hass, infrared_entity)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_remove_command({COMMAND_NAME: "MISSING"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "command_not_found"


async def test_remove_command_without_remote_aborts(hass: HomeAssistant) -> None:
    """Test remove command aborts when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_remove_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_legacy_list_storage_is_preserved(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test old list-based entries still write list-based options."""
    result = await _init_options_flow(hass, config_entry, SOURCE_EDIT_REMOTE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_REMOTE_NAME: "Updated TV",
            CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_NAME] == "Updated TV"


async def test_edit_remote_without_remote_aborts(hass: HomeAssistant) -> None:
    """Test edit remote aborts when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_edit_remote()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_edit_remote_rejects_unavailable_infrared_entity_direct(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test edit remote rejects an unavailable infrared entity."""
    entry = _single_entry(hass, infrared_entity)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    with patch(
        "homeassistant.components.virtual_remote.options_flow.available_infrared_entities",
        return_value={"infrared.test_ir": "Test IR"},
    ):
        result = await flow.async_step_edit_remote(
            {
                CONF_REMOTE_NAME: "TV",
                CONF_INFRARED_ENTITY_ID: "infrared.missing",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable"}


async def test_select_command_for_edit_without_remote_aborts(
    hass: HomeAssistant,
) -> None:
    """Test selecting command to edit aborts when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_select_command_for_edit()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_remove_command_keeps_remaining_commands(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test removing one command keeps the remaining commands."""
    entry = _single_entry(hass, infrared_entity)
    entry.options[CONF_REMOTE_COMMANDS]["POWER_OFF"] = RAW_COMMAND

    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_remove_command({COMMAND_NAME: "POWER_ON"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REMOTE_COMMANDS] == {"POWER_OFF": RAW_COMMAND}


def test_commands_returns_empty_without_remote(hass: HomeAssistant) -> None:
    """Test command helper returns empty when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)

    assert flow._commands == {}


def test_create_options_entry_without_remote_aborts(hass: HomeAssistant) -> None:
    """Test create options entry aborts when the entry has no remote."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)

    result = flow._create_options_entry()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"
