"""Tests for iTach IP2IR options flow."""

from typing import Any, cast

import pytest

from homeassistant.components.itachip2ir.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.components.itachip2ir.options_flow import (
    COMMAND_DATA,
    COMMAND_NAME,
    SOURCE_ADD_COMMAND,
    SOURCE_ADD_REMOTE,
    SOURCE_CHANGE_REMOTE_INFRARED_ENTITY,
    SOURCE_EDIT_COMMAND,
    SOURCE_REFRESH_INFRARED_PORTS,
    SOURCE_REMOVE_COMMAND,
    SOURCE_REMOVE_REMOTE,
    _normalize_command_name,
    _slugify_remote_id,
)
from homeassistant.components.itachip2ir.pyitach import ItachConnectionError, ItachError
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


def _entry(**kwargs):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="GlobalCache_000C1E123456",
        data={
            "host": "192.168.1.211",
            "port": 4998,
            "ir_module": 1,
            "ir_ports": 3,
            "ir_enabled_ports": [1, 3],
            "ir_connector_modes": {
                "1": "IR",
                "2": "SENSOR",
                "3": "IR_BLASTER",
            },
        },
        title="iTach IP2IR",
        **kwargs,
    )


def _infrared_entity_id(port: int = 1) -> str:
    """Return a stable infrared entity id for a test port."""
    return f"infrared.port_{port}"


def _register_infrared_entities(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Register iTach-owned infrared entities for option selectors."""
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for port in entry.data["ir_enabled_ports"]:
        registry.async_get_or_create(
            "infrared",
            DOMAIN,
            f"{entry.unique_id}_port_{port}",
            suggested_object_id=f"port_{port}",
            config_entry=entry,
        )


def _remote(
    remote_id: str = "living_room_tv",
    name: str = "Living Room TV",
    port: int = 1,
    commands: dict[str, str] | None = None,
) -> dict:
    """Create a virtual remote options dict."""
    remote: dict[str, object] = {
        CONF_REMOTE_ID: remote_id,
        CONF_REMOTE_NAME: name,
        CONF_INFRARED_ENTITY_ID: _infrared_entity_id(port),
    }
    if commands is not None:
        remote[CONF_REMOTE_COMMANDS] = commands
    return remote


def _schema_default(result: Any, field: str) -> Any:
    """Return the configured default for a form field."""
    data_schema = result["data_schema"]
    assert data_schema is not None
    for marker in data_schema.schema:
        if getattr(marker, "schema", marker) == field:
            return marker.default()
    raise AssertionError(f"Field {field} not found in schema")


async def test_options_flow_shows_add_remote_menu(hass: HomeAssistant) -> None:
    """Test options flow shows virtual remote menu."""
    entry = _entry()
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert result["menu_options"] == [SOURCE_REFRESH_INFRARED_PORTS, SOURCE_ADD_REMOTE]


async def test_options_flow_shows_full_menu_when_remotes_exist(
    hass: HomeAssistant,
) -> None:
    """Test options flow shows remote and command management choices."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert result["menu_options"] == [
        SOURCE_REFRESH_INFRARED_PORTS,
        SOURCE_ADD_REMOTE,
        SOURCE_REMOVE_REMOTE,
        SOURCE_CHANGE_REMOTE_INFRARED_ENTITY,
        SOURCE_ADD_COMMAND,
        SOURCE_EDIT_COMMAND,
        SOURCE_REMOVE_COMMAND,
    ]


async def test_options_flow_adds_virtual_remote(hass: HomeAssistant) -> None:
    """Test adding a virtual remote."""
    entry = _entry()
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_remote"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES] == [
        {
            CONF_REMOTE_ID: "living_room_tv",
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
        }
    ]


async def test_options_flow_add_remote_rejects_empty_name(hass: HomeAssistant) -> None:
    """Test adding a virtual remote rejects an empty name."""
    entry = _entry()
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "   ",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_remote"
    assert result["errors"] == {CONF_REMOTE_NAME: "remote_name_required"}


async def test_options_flow_allows_multiple_remotes_on_same_infrared_entity(
    hass: HomeAssistant,
) -> None:
    """Test multiple virtual remotes may share one infrared transmitter."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote(port=1)]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "Bedroom TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES] == [
        _remote(port=1),
        {
            CONF_REMOTE_ID: "bedroom_tv",
            CONF_REMOTE_NAME: "Bedroom TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
        },
    ]


async def test_options_flow_removes_virtual_remote(hass: HomeAssistant) -> None:
    """Test removing a virtual remote."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REMOVE_REMOTE},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "remove_remote"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES] == []


async def test_options_flow_remove_remote_aborts_without_remotes(
    hass: HomeAssistant,
) -> None:
    """Test removing a virtual remote aborts when none exist."""
    entry = _entry()
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REMOVE_REMOTE},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_virtual_remotes"


async def test_options_flow_rejects_duplicate_name(hass: HomeAssistant) -> None:
    """Test duplicate virtual remote names are rejected."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3),
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_REMOTE_NAME: "remote_name_exists"}


async def test_options_flow_rejects_duplicate_slug_id(hass: HomeAssistant) -> None:
    """Test names normalizing to an existing id are rejected."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "Living Room TV!!!",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3),
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_REMOTE_NAME: "remote_name_exists"}


async def test_options_flow_add_remote_still_offers_used_infrared_entities(
    hass: HomeAssistant,
) -> None:
    """Test used infrared transmitters remain selectable for additional remotes."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(remote_id="tv", name="TV", port=1),
                _remote(remote_id="amp", name="Amplifier", port=3),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_remote"


async def test_options_flow_adds_named_command(hass: HomeAssistant) -> None:
    """Test adding a named command to a virtual remote."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_remote_for_command"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "add_command"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            COMMAND_NAME: "Power On",
            COMMAND_DATA: "0000 006D 0001 0000 0010 0020",
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES] == [
        {
            CONF_REMOTE_ID: "living_room_tv",
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
            CONF_REMOTE_COMMANDS: {
                "power_on": "0000 006D 0001 0000 0010 0020",
            },
        }
    ]


async def test_options_flow_add_command_replaces_existing_command(
    hass: HomeAssistant,
) -> None:
    """Test adding a named command replaces an existing command value."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "old"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power On", COMMAND_DATA: "100,200"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] == {
        "power_on": "100,200",
    }


async def test_options_flow_add_command_rejects_empty_fields(
    hass: HomeAssistant,
) -> None:
    """Test adding a named command validates name and data."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "   ", COMMAND_DATA: "   "},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_command"
    assert result["errors"] == {
        COMMAND_NAME: "command_name_required",
        COMMAND_DATA: "command_data_required",
    }


async def test_options_flow_add_command_preserves_input_after_error(
    hass: HomeAssistant,
) -> None:
    """Test invalid command data does not clear submitted form values."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            COMMAND_NAME: "Power Toggle",
            COMMAND_DATA: "100,,200",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_command"
    assert result["errors"] == {COMMAND_DATA: "invalid_command"}
    assert _schema_default(result, COMMAND_NAME) == "Power Toggle"
    assert _schema_default(result, COMMAND_DATA) == "100,,200"


async def test_options_flow_add_command_aborts_without_remotes(
    hass: HomeAssistant,
) -> None:
    """Test adding a named command aborts when no remotes exist."""
    entry = _entry()
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_virtual_remotes"


async def test_options_flow_edits_named_command(hass: HomeAssistant) -> None:
    """Test editing a named command on a virtual remote."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "100,200", "power_off": "300,400"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_remote_for_command_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_command_for_edit"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "edit_command"
    assert _schema_default(result, COMMAND_NAME) == "power_on"
    assert _schema_default(result, COMMAND_DATA) == "100,200"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power Toggle", COMMAND_DATA: "500,600"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] == {
        "power_off": "300,400",
        "power_toggle": "500,600",
    }


async def test_options_flow_edit_command_rejects_duplicate_name(
    hass: HomeAssistant,
) -> None:
    """Test editing a command rejects renaming over another command."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "100,200", "power_off": "300,400"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power Off", COMMAND_DATA: "500,600"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "edit_command"
    assert result["errors"] == {COMMAND_NAME: "command_name_exists"}
    assert _schema_default(result, COMMAND_NAME) == "Power Off"
    assert _schema_default(result, COMMAND_DATA) == "500,600"


async def test_options_flow_edit_command_rejects_invalid_data(
    hass: HomeAssistant,
) -> None:
    """Test editing a command preserves submitted values after validation error."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "100,200"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power On", COMMAND_DATA: "100,,200"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "edit_command"
    assert result["errors"] == {COMMAND_DATA: "invalid_command"}
    assert _schema_default(result, COMMAND_NAME) == "Power On"
    assert _schema_default(result, COMMAND_DATA) == "100,,200"


async def test_options_flow_edit_command_aborts_without_commands(
    hass: HomeAssistant,
) -> None:
    """Test editing a command aborts when no remote has commands."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_remote_commands"


async def test_options_flow_edit_command_aborts_when_command_missing(
    hass: HomeAssistant,
) -> None:
    """Test editing aborts if the selected command disappears mid-flow."""
    entry = _entry(
        options={CONF_VIRTUAL_REMOTES: [_remote(commands={"power_on": "100,200"})]}
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )

    flow = cast(Any, hass.config_entries.options._progress[result["flow_id"]])
    flow._virtual_remotes[0][CONF_REMOTE_COMMANDS] = {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on", COMMAND_DATA: "500,600"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_remote_commands"


async def test_options_flow_removes_named_command(hass: HomeAssistant) -> None:
    """Test removing a named command from a virtual remote."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "on", "power_off": "off"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REMOVE_COMMAND},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_remote_for_command_removal"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "remove_command"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] == {
        "power_off": "off",
    }


async def test_options_flow_remove_command_aborts_without_commands(
    hass: HomeAssistant,
) -> None:
    """Test removing a command aborts when no remote has commands."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REMOVE_COMMAND},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_remote_commands"


async def test_options_flow_preserves_unrelated_options(hass: HomeAssistant) -> None:
    """Test creating options preserves unrelated option values."""
    entry = _entry(options={"other_option": True})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"]["other_option"] is True


def test_slugify_remote_id_normalizes_names() -> None:
    """Test virtual remote id normalization."""
    assert _slugify_remote_id(" Living Room TV!!! ") == "living_room_tv"
    assert _slugify_remote_id("!!!") == "remote"


def test_normalize_command_name_normalizes_names() -> None:
    """Test command name normalization."""
    assert _normalize_command_name("Power On") == "power_on"


async def test_options_flow_add_command_without_selected_remote_redirects(
    hass: HomeAssistant,
) -> None:
    """Test add command redirects to remote selection when none is selected."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "select_remote_for_command"


async def test_options_flow_add_command_aborts_when_selected_remote_missing(
    hass: HomeAssistant,
) -> None:
    """Test add command aborts if the selected remote is removed mid-flow."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    flow = cast(Any, hass.config_entries.options._progress[result["flow_id"]])
    flow._virtual_remotes = []

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power", COMMAND_DATA: "100,200"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "remote_not_found"


async def test_options_flow_remove_command_aborts_when_selected_remote_missing(
    hass: HomeAssistant,
) -> None:
    """Test remove command aborts if the selected remote is removed mid-flow."""
    entry = _entry(
        options={CONF_VIRTUAL_REMOTES: [_remote(commands={"power": "100,200"})]}
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REMOVE_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    flow = cast(Any, hass.config_entries.options._progress[result["flow_id"]])
    flow._virtual_remotes = []

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "remote_not_found"


class FakeItachClient:
    """Fake iTach client for options flow port refresh tests."""

    module_error: Exception | None = None
    connector_modes: dict[int, str] = {1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}
    closed = False

    def __init__(self, host: str, port: int) -> None:
        """Initialize the fake client."""
        self.host = host
        self.port = port
        type(self).closed = False

    async def async_get_ir_module(self) -> tuple[int, int]:
        """Return fake IR module information."""
        if type(self).module_error is not None:
            module_error = type(self).module_error
            assert isinstance(module_error, BaseException)
            raise module_error
        return (1, 3)

    async def async_get_ir_connector_modes(
        self,
        module: int,
        connectors: int,
    ) -> dict[int, str]:
        """Return fake connector modes."""
        return dict(type(self).connector_modes)

    async def close(self) -> None:
        """Close the fake client."""
        type(self).closed = True


def _patch_refresh_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    connector_modes: dict[int, str] | None = None,
    module_error: Exception | None = None,
) -> None:
    """Patch the options flow iTach client for refresh tests."""
    FakeItachClient.connector_modes = (
        {1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}
        if connector_modes is None
        else connector_modes
    )
    FakeItachClient.module_error = module_error
    FakeItachClient.closed = False
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        FakeItachClient,
    )


async def test_options_flow_refresh_infrared_ports_success(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test refreshing infrared ports validates and forces an options reload."""
    _patch_refresh_client(monkeypatch)
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "refresh_infrared_ports"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES] == [_remote()]
    assert "last_port_refresh" in result["data"]
    assert FakeItachClient.closed


async def test_options_flow_refresh_infrared_ports_cannot_connect(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test refreshing infrared ports reports connection failures."""
    _patch_refresh_client(
        monkeypatch,
        module_error=ItachConnectionError("offline"),
    )
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    assert FakeItachClient.closed


async def test_options_flow_refresh_infrared_ports_no_ir_ports(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test refreshing infrared ports reports no current IR outputs."""
    _patch_refresh_client(
        monkeypatch,
        connector_modes={1: "SENSOR", 2: "SENSOR", 3: "SENSOR"},
    )
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "no_ir_ports"}
    assert FakeItachClient.closed


async def test_options_flow_refresh_infrared_ports_unknown_error(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test refreshing infrared ports reports unexpected iTach errors."""
    _patch_refresh_client(
        monkeypatch,
        module_error=ItachError("bad response"),
    )
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
    assert FakeItachClient.closed


async def test_options_flow_changes_remote_infrared_entity(hass: HomeAssistant) -> None:
    """Test changing a virtual remote's backing infrared entity."""
    entry = _entry(
        options={CONF_VIRTUAL_REMOTES: [_remote(commands={"power": "100,200"})]}
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_CHANGE_REMOTE_INFRARED_ENTITY},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_remote_for_infrared_entity"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "change_remote_infrared_entity"
    assert _schema_default(result, CONF_INFRARED_ENTITY_ID) == _infrared_entity_id(1)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3)},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES] == [
        {
            CONF_REMOTE_ID: "living_room_tv",
            CONF_REMOTE_NAME: "Living Room TV",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3),
            CONF_REMOTE_COMMANDS: {"power": "100,200"},
        }
    ]


async def test_options_flow_change_remote_infrared_entity_rejects_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test changing a backing infrared entity rejects unavailable selections."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_CHANGE_REMOTE_INFRARED_ENTITY},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "change_remote_infrared_entity"

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_INFRARED_ENTITY_ID: "infrared.not_this_entry"},
        )


async def test_options_flow_change_remote_infrared_entity_aborts_without_remotes(
    hass: HomeAssistant,
) -> None:
    """Test changing backing infrared entity aborts without virtual remotes."""
    entry = _entry()
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_CHANGE_REMOTE_INFRARED_ENTITY},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_virtual_remotes"


async def test_options_flow_change_remote_infrared_entity_aborts_when_missing(
    hass: HomeAssistant,
) -> None:
    """Test changing backing infrared entity aborts if remote disappears mid-flow."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_CHANGE_REMOTE_INFRARED_ENTITY},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    flow = cast(Any, hass.config_entries.options._progress[result["flow_id"]])
    flow._virtual_remotes = []

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3)},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "remote_not_found"


async def test_options_flow_add_remote_aborts_without_available_infrared_entities(
    hass: HomeAssistant,
) -> None:
    """Test adding a virtual remote aborts when no infrared entities exist."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_available_infrared_entities"


async def test_options_flow_change_remote_infrared_entity_aborts_without_available_entities(
    hass: HomeAssistant,
) -> None:
    """Test changing a remote infrared entity aborts when none are available."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_CHANGE_REMOTE_INFRARED_ENTITY},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_available_infrared_entities"


async def test_options_flow_add_command_rejects_empty_command_name(
    hass: HomeAssistant,
) -> None:
    """Test adding a command rejects an empty command name when data is present."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "   ", COMMAND_DATA: "100,200"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_command"
    assert result["errors"] == {COMMAND_NAME: "command_name_required"}


async def test_options_flow_edit_command_rejects_empty_command_name(
    hass: HomeAssistant,
) -> None:
    """Test editing a command rejects an empty new command name."""
    entry = _entry(
        options={CONF_VIRTUAL_REMOTES: [_remote(commands={"power_on": "100,200"})]}
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "   ", COMMAND_DATA: "100,200"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "edit_command"
    assert result["errors"] == {COMMAND_NAME: "command_name_required"}


async def test_options_flow_edit_command_rejects_empty_command_data(
    hass: HomeAssistant,
) -> None:
    """Test editing a command rejects empty command data."""
    entry = _entry(
        options={CONF_VIRTUAL_REMOTES: [_remote(commands={"power_on": "100,200"})]}
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power On", COMMAND_DATA: "   "},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "edit_command"
    assert result["errors"] == {COMMAND_DATA: "command_data_required"}


async def test_options_flow_adds_named_command_from_json_timing_array(
    hass: HomeAssistant,
) -> None:
    """Test adding a named command accepts a bare JSON timing array."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            COMMAND_NAME: "Power JSON",
            COMMAND_DATA: "[9000, 4500, 560, 560]",
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] == {
        "power_json": "[9000, 4500, 560, 560]",
    }


async def test_options_flow_add_remote_preserves_input_after_duplicate_error(
    hass: HomeAssistant,
) -> None:
    """Test duplicate remote validation keeps submitted values visible."""
    entry = _entry(options={CONF_VIRTUAL_REMOTES: [_remote()]})
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_ADD_REMOTE},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_REMOTE_NAME: "Living Room TV!!!",
            CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3),
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "add_remote"
    assert result["errors"] == {CONF_REMOTE_NAME: "remote_name_exists"}
    assert _schema_default(result, CONF_REMOTE_NAME) == "Living Room TV!!!"
    assert _schema_default(result, CONF_INFRARED_ENTITY_ID) == _infrared_entity_id(3)


async def test_options_flow_edit_command_updates_same_normalized_name(
    hass: HomeAssistant,
) -> None:
    """Test editing a command may keep the same normalized command name."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "100,200"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power On", COMMAND_DATA: "300,400"},
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_COMMANDS] == {
        "power_on": "300,400",
    }


async def test_options_flow_remove_command_rejects_unknown_command(
    hass: HomeAssistant,
) -> None:
    """Test removing an unknown command is rejected by the selector schema."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "100,200"}),
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REMOVE_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={COMMAND_NAME: "missing_command"},
        )


async def test_options_flow_edit_command_aborts_when_remote_removed_before_command_select(
    hass: HomeAssistant,
) -> None:
    """Test edit command aborts if the selected remote disappears mid-flow."""
    entry = _entry(
        options={CONF_VIRTUAL_REMOTES: [_remote(commands={"power_on": "100,200"})]}
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )

    flow = cast(Any, hass.config_entries.options._progress[result["flow_id"]])
    flow._virtual_remotes = []

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "remote_not_found"


async def test_options_flow_edit_command_aborts_when_selected_command_removed(
    hass: HomeAssistant,
) -> None:
    """Test edit command aborts if the selected command is removed mid-flow."""
    entry = _entry(
        options={
            CONF_VIRTUAL_REMOTES: [
                _remote(commands={"power_on": "100,200", "power_off": "300,400"})
            ]
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_EDIT_COMMAND},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_REMOTE_ID: "living_room_tv"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "power_on"},
    )

    flow = cast(Any, hass.config_entries.options._progress[result["flow_id"]])
    flow._virtual_remotes[0][CONF_REMOTE_COMMANDS] = {"power_off": "300,400"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={COMMAND_NAME: "Power On", COMMAND_DATA: "500,600"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "command_not_found"


async def test_options_flow_refresh_infrared_ports_uses_options_host_and_port(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test port refresh validates against overridden host and port options."""

    class CapturingClient(FakeItachClient):
        last_host: str | None = None
        last_port: int | None = None

        def __init__(self, host: str, port: int) -> None:
            super().__init__(host, port)
            type(self).last_host = host
            type(self).last_port = port

    FakeItachClient.connector_modes = {1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}
    FakeItachClient.module_error = None
    FakeItachClient.closed = False
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.options_flow.ItachClient",
        CapturingClient,
    )
    entry = _entry(
        options={
            "host": "192.168.1.250",
            "port": 5998,
            CONF_VIRTUAL_REMOTES: [_remote()],
        }
    )
    _register_infrared_entities(hass, entry)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        context={"source": SOURCE_REFRESH_INFRARED_PORTS},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] == "create_entry"
    assert CapturingClient.last_host == "192.168.1.250"
    assert CapturingClient.last_port == 5998
    assert CapturingClient.closed


def test_normalize_command_name_returns_empty_for_symbols_only() -> None:
    """Test command names do not silently fallback to a default value."""
    assert _normalize_command_name(" !!! ") == ""
