"""Tests for the Virtual Remote options flow."""

from typing import cast

import pytest

from homeassistant import config_entries
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
    SOURCE_ADD_REMOTE,
    SOURCE_EDIT_COMMAND,
    SOURCE_EDIT_REMOTE,
    SOURCE_MANAGE_COMMANDS,
    SOURCE_REMOVE_COMMAND,
    SOURCE_REMOVE_REMOTE,
    VirtualRemoteOptionsFlow,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import INFRARED_ENTITY_ID, RAW_COMMAND

from tests.common import MockConfigEntry


async def _init_options_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    source: str | None = None,
) -> ConfigFlowResult:
    """Initialize the options flow."""
    context: config_entries.ConfigFlowContext = {
        "source": "init",
        "entry_id": entry.entry_id,
    }
    if source is not None:
        context["source"] = source
    return await hass.config_entries.options.async_init(
        entry.entry_id,
        context=context,
    )


async def test_options_menu(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test options menu."""
    result = await _init_options_flow(hass, config_entry)

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [
        SOURCE_ADD_REMOTE,
        SOURCE_EDIT_REMOTE,
        SOURCE_REMOVE_REMOTE,
        SOURCE_MANAGE_COMMANDS,
    ]


async def test_options_menu_only_add_without_remotes(
    hass: HomeAssistant, infrared_entity: str
) -> None:
    """Test menu with no configured remotes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_VIRTUAL_REMOTES: []},
    )
    entry.add_to_hass(hass)

    result = await _init_options_flow(hass, entry)

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [SOURCE_ADD_REMOTE]


async def test_add_remote_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test adding a remote."""
    result = await _init_options_flow(hass, config_entry, SOURCE_ADD_REMOTE)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_REMOTE_NAME: "Bedroom TV",
            CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    remotes = result["data"][CONF_VIRTUAL_REMOTES]
    assert remotes[-1] == {
        CONF_REMOTE_ID: "bedroom_tv",
        CONF_REMOTE_NAME: "Bedroom TV",
        CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
    }


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {CONF_REMOTE_NAME: "", CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID},
            {CONF_REMOTE_NAME: "remote_name_required"},
        ),
        (
            {
                CONF_REMOTE_NAME: "Living Room TV",
                CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
            },
            {CONF_REMOTE_NAME: "remote_name_exists"},
        ),
    ],
)
async def test_add_remote_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test adding a remote validation errors."""
    result = await _init_options_flow(hass, config_entry, SOURCE_ADD_REMOTE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_add_remote_no_infrared_entities(hass: HomeAssistant) -> None:
    """Test adding a remote aborts without infrared entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_VIRTUAL_REMOTES: []},
    )
    entry.add_to_hass(hass)

    result = await _init_options_flow(hass, entry, SOURCE_ADD_REMOTE)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_edit_remote_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test editing a remote."""
    result = await _init_options_flow(hass, config_entry, SOURCE_EDIT_REMOTE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )
    assert result["step_id"] == "edit_remote"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_REMOTE_NAME: "Updated TV",
            CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    remote = result["data"][CONF_VIRTUAL_REMOTES][0]
    assert remote[CONF_REMOTE_NAME] == "Updated TV"


async def test_edit_remote_with_stale_current_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test editing preserves stale current entity as allowed default."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0][CONF_INFRARED_ENTITY_ID] = (
        "infrared.stale"
    )

    result = await _init_options_flow(hass, config_entry, SOURCE_EDIT_REMOTE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_REMOTE_NAME: "Updated TV",
            CONF_INFRARED_ENTITY_ID: "infrared.stale",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_VIRTUAL_REMOTES][0][CONF_INFRARED_ENTITY_ID]
        == "infrared.stale"
    )


async def test_remove_remote(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test removing a remote."""
    result = await _init_options_flow(hass, config_entry, SOURCE_REMOVE_REMOTE)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VIRTUAL_REMOTES] == []


async def test_remove_remote_aborts_when_remote_is_not_found(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test removing a stale or missing remote aborts without writing options."""
    result = await _init_options_flow(hass, config_entry, SOURCE_REMOVE_REMOTE)

    flow = cast(
        VirtualRemoteOptionsFlow,
        hass.config_entries.options._progress[result["flow_id"]],
    )
    flow._virtual_remotes = []

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_remote_steps_abort_without_remotes(
    hass: HomeAssistant, infrared_entity: str
) -> None:
    """Test remote steps abort without configured remotes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_VIRTUAL_REMOTES: []},
    )
    entry.add_to_hass(hass)

    for source in (SOURCE_EDIT_REMOTE, SOURCE_REMOVE_REMOTE, SOURCE_MANAGE_COMMANDS):
        result = await _init_options_flow(hass, entry, source)
        if source == SOURCE_MANAGE_COMMANDS:
            assert result["type"] is FlowResultType.MENU
        else:
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "no_virtual_remotes"


async def test_manage_commands_menu(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test manage commands menu."""
    result = await _init_options_flow(hass, config_entry, SOURCE_MANAGE_COMMANDS)

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [
        SOURCE_ADD_COMMAND,
        SOURCE_EDIT_COMMAND,
        SOURCE_REMOVE_COMMAND,
    ]


async def test_add_command_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test adding a command."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] = {}
    result = await _init_options_flow(hass, config_entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "power on", COMMAND_DATA: RAW_COMMAND},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS]["POWER_ON"]
        == RAW_COMMAND
    )


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {COMMAND_NAME: "", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_required"},
        ),
        (
            {COMMAND_NAME: "POWER_ON", COMMAND_DATA: ""},
            {COMMAND_DATA: "command_data_required"},
        ),
        (
            {COMMAND_NAME: "POWER_ON", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_exists"},
        ),
        ({COMMAND_NAME: "NEW", COMMAND_DATA: "bad"}, {COMMAND_DATA: "invalid_command"}),
    ],
)
async def test_add_command_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test adding command errors."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_add_command(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_edit_command_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test editing a command."""
    result = await _init_options_flow(hass, config_entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "POWER_ON"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "NEW_POWER", COMMAND_DATA: RAW_COMMAND},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    commands = result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS]
    assert "POWER_ON" not in commands
    assert commands["NEW_POWER"] == RAW_COMMAND


async def test_remove_command_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test removing a command."""
    result = await _init_options_flow(hass, config_entry, SOURCE_MANAGE_COMMANDS)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": SOURCE_REMOVE_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {COMMAND_NAME: "POWER_ON"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        "POWER_ON" not in result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS]
    )


async def test_remove_last_command_removes_commands_key(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test removing the last command removes the commands key."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] = {
        "POWER_ON": RAW_COMMAND
    }
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_remove_command({COMMAND_NAME: "POWER_ON"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_REMOTE_COMMANDS not in result["data"][CONF_VIRTUAL_REMOTES][0]


async def test_command_steps_abort_when_no_commands(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test command edit/remove abort when no commands exist."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0].pop(CONF_REMOTE_COMMANDS, None)

    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass

    assert (await flow.async_step_select_remote_for_command_edit())[
        "reason"
    ] == "no_remote_commands"
    assert (await flow.async_step_select_remote_for_command_removal())[
        "reason"
    ] == "no_remote_commands"


async def test_direct_step_fallbacks_and_missing_selected_remote(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test direct step fallbacks and missing selection aborts."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass

    assert (await flow.async_step_edit_remote())["step_id"] == "select_remote_for_edit"
    assert (await flow.async_step_add_command())[
        "step_id"
    ] == "select_remote_for_command"
    assert (await flow.async_step_select_command_for_edit())[
        "step_id"
    ] == "select_remote_for_command_edit"
    assert (await flow.async_step_remove_command())[
        "step_id"
    ] == "select_remote_for_command_removal"

    flow._selected_remote_id = "missing"
    assert (
        await flow.async_step_edit_remote(
            {CONF_REMOTE_NAME: "A", CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID}
        )
    )["reason"] == "remote_not_found"
    assert (
        await flow.async_step_add_command(
            {COMMAND_NAME: "A", COMMAND_DATA: RAW_COMMAND}
        )
    )["reason"] == "remote_not_found"
    assert (
        await flow.async_step_edit_command(
            {COMMAND_NAME: "A", COMMAND_DATA: RAW_COMMAND}
        )
    )["reason"] == "remote_not_found"
    assert (await flow.async_step_remove_command({COMMAND_NAME: "A"}))[
        "reason"
    ] == "remote_not_found"


async def test_add_remote_unavailable_infrared_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test add remote reports unavailable infrared entity."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass

    result = await flow.async_step_add_remote(
        {
            CONF_REMOTE_NAME: "Bedroom TV",
            CONF_INFRARED_ENTITY_ID: "infrared.missing",
        }
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable"}


async def test_edit_remote_aborts_without_infrared_entities(
    hass: HomeAssistant,
) -> None:
    """Test edit remote aborts when no infrared entities are available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "living_room_tv",
                    CONF_REMOTE_NAME: "Living Room TV",
                    CONF_INFRARED_ENTITY_ID: "infrared.missing",
                }
            ]
        },
    )
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_edit_remote()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {CONF_REMOTE_NAME: "", CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID},
            {CONF_REMOTE_NAME: "remote_name_required"},
        ),
        (
            {
                CONF_REMOTE_NAME: "Bedroom TV",
                CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
            },
            {CONF_REMOTE_NAME: "remote_name_exists"},
        ),
        (
            {
                CONF_REMOTE_NAME: "Updated TV",
                CONF_INFRARED_ENTITY_ID: "infrared.missing",
            },
            {CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable"},
        ),
    ],
)
async def test_edit_remote_validation_errors(
    hass: HomeAssistant,
    infrared_entity: str,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test edit remote validation errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "living_room_tv",
                    CONF_REMOTE_NAME: "Living Room TV",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                },
                {
                    CONF_REMOTE_ID: "bedroom_tv",
                    CONF_REMOTE_NAME: "Bedroom TV",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                },
            ]
        },
    )
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_edit_remote(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


@pytest.mark.parametrize(
    ("source", "expected_option"),
    [
        (SOURCE_ADD_COMMAND, "add_command"),
        (SOURCE_EDIT_COMMAND, "edit_command"),
        (SOURCE_REMOVE_COMMAND, "remove_command"),
    ],
)
async def test_manage_commands_source_shortcuts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    source: str,
    expected_option: str,
) -> None:
    """Test command source shortcuts."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass

    result = await flow.async_step_manage_commands()

    assert result["type"] is FlowResultType.MENU
    assert expected_option in result["menu_options"]


async def test_select_remote_for_command_aborts_without_remotes(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test add-command remote selection aborts without remotes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_VIRTUAL_REMOTES: []},
    )
    entry.add_to_hass(hass)
    flow = VirtualRemoteOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_select_remote_for_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_select_command_for_edit_missing_remote_with_input(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test command selection aborts when selected remote is missing."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "missing"

    result = await flow.async_step_select_command_for_edit({COMMAND_NAME: "POWER_ON"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remote_not_found"


async def test_select_command_for_edit_aborts_when_selected_remote_has_no_commands(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test command selection aborts when selected remote has no commands."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0].pop(CONF_REMOTE_COMMANDS, None)
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_select_command_for_edit()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remote_commands"


async def test_edit_command_aborts_when_selected_remote_has_no_commands(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test edit command aborts when selected remote has no commands."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0].pop(CONF_REMOTE_COMMANDS, None)
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_edit_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remote_commands"


async def test_edit_command_missing_selected_command_falls_back_to_selector(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test edit command falls back to selector when selected command is missing."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"
    flow._selected_command_name = "MISSING"

    result = await flow.async_step_edit_command()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_command_for_edit"


async def test_edit_command_aborts_when_selected_command_missing_with_input(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test edit command aborts when selected command is missing on submit."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"
    flow._selected_command_name = "MISSING"

    result = await flow.async_step_edit_command(
        {COMMAND_NAME: "NEW", COMMAND_DATA: RAW_COMMAND}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "command_not_found"


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {COMMAND_NAME: "", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_required"},
        ),
        (
            {COMMAND_NAME: "POWER_ON", COMMAND_DATA: ""},
            {COMMAND_DATA: "command_data_required"},
        ),
        (
            {COMMAND_NAME: "POWER_OFF", COMMAND_DATA: RAW_COMMAND},
            {COMMAND_NAME: "command_name_exists"},
        ),
        (
            {COMMAND_NAME: "POWER_ON", COMMAND_DATA: "bad"},
            {COMMAND_DATA: "invalid_command"},
        ),
    ],
)
async def test_edit_command_validation_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test edit command validation errors."""
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"
    flow._selected_command_name = "POWER_ON"

    result = await flow.async_step_edit_command(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_remove_command_aborts_when_selected_remote_has_no_commands(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test remove command aborts when selected remote has no commands."""
    config_entry.options[CONF_VIRTUAL_REMOTES][0].pop(CONF_REMOTE_COMMANDS, None)
    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    flow._selected_remote_id = "living_room_tv"

    result = await flow.async_step_remove_command()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remote_commands"


async def test_remove_remote_aborts_when_selected_remote_disappears(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test remove remote aborts when selected remote disappeared after form display."""
    result = await _init_options_flow(hass, config_entry, SOURCE_REMOVE_REMOTE)

    flow = cast(
        VirtualRemoteOptionsFlow,
        hass.config_entries.options._progress[result["flow_id"]],
    )
    flow._virtual_remotes = [
        {
            CONF_REMOTE_ID: "other",
            CONF_REMOTE_NAME: "Other",
            CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
        }
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_REMOTE_ID: "living_room_tv"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remote_not_found"


async def test_manage_commands_menu_contains_command_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test manage commands menu contains command actions."""
    result = await _init_options_flow(
        hass,
        config_entry,
        SOURCE_MANAGE_COMMANDS,
    )

    assert result["type"] is FlowResultType.MENU
    assert "add_command" in result["menu_options"]
    assert "edit_command" in result["menu_options"]
    assert "remove_command" in result["menu_options"]


@pytest.mark.parametrize(
    ("source", "expected_step", "needs_commands"),
    [
        (SOURCE_ADD_COMMAND, "select_remote_for_command", False),
        (SOURCE_EDIT_COMMAND, "select_remote_for_command_edit", True),
        (SOURCE_REMOVE_COMMAND, "select_remote_for_command_removal", True),
    ],
)
async def test_manage_commands_source_shortcuts_cover_direct_branches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    expected_step: str,
    needs_commands: bool,
) -> None:
    """Test command source shortcuts route to command selection steps."""
    if needs_commands:
        config_entry.options[CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] = {
            "POWER_ON": RAW_COMMAND
        }

    flow = VirtualRemoteOptionsFlow(config_entry)
    flow.hass = hass
    monkeypatch.setattr(
        type(flow),
        "context",
        property(lambda _flow: {"source": source}),
    )

    result = await flow.async_step_manage_commands()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step
