"""Tests for virtual remote helper functions."""

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
)
from homeassistant.components.virtual_remote.helpers import (
    available_infrared_entities,
    command_options,
    find_command_key,
    infrared_entity_field,
    infrared_entity_field_with_current,
    infrared_entity_selector,
    normalize_command_name,
    normalize_remote_id,
    normalize_virtual_remotes,
    remote_options,
    remotes_with_commands,
    unique_remote_id,
    virtual_remote_from_config_entry_data,
    virtual_remotes_from_config_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, selector

from tests.common import MockConfigEntry


def _field_default(field: vol.Required) -> Any:
    """Return a voluptuous field default for typing-friendly tests."""
    default = cast(Any, field.default)
    try:
        return default()
    except TypeError:
        return None


def test_available_infrared_entities(hass: HomeAssistant) -> None:
    """Test available infrared entity selector options."""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "infrared",
        "test",
        "ir_b",
        suggested_object_id="ir_b",
        original_name="IR B",
    )
    registry.async_get_or_create(
        "infrared",
        "test",
        "ir_a",
        suggested_object_id="ir_a",
        original_name="IR A",
    )
    registry.async_get_or_create(
        "infrared",
        "test",
        "ir_disabled",
        suggested_object_id="ir_disabled",
        original_name="Disabled IR",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    registry.async_get_or_create(
        "light",
        "test",
        "light",
        suggested_object_id="ignored",
        original_name="Ignored",
    )

    options = available_infrared_entities(hass)

    assert list(options) == ["infrared.ir_a", "infrared.ir_b"]
    assert options["infrared.ir_a"]["label"] == "IR A"


def test_infrared_entity_selector_includes_current_missing_entity() -> None:
    """Test selector includes stale current entity."""
    available: dict[str, selector.SelectOptionDict] = {
        "infrared.valid": selector.SelectOptionDict(
            value="infrared.valid",
            label="Valid",
        )
    }

    selector_obj = infrared_entity_selector(
        available,
        current_entity_id="infrared.missing",
    )

    options = cast(list[selector.SelectOptionDict], selector_obj.config["options"])
    values = [option["value"] for option in options]
    assert values == ["infrared.valid", "infrared.missing"]


def test_infrared_entity_field_defaults() -> None:
    """Test selector field defaults."""
    available: dict[str, selector.SelectOptionDict] = {
        "infrared.valid": selector.SelectOptionDict(
            value="infrared.valid",
            label="Valid",
        )
    }

    assert (
        _field_default(infrared_entity_field("infrared.valid", available))
        == "infrared.valid"
    )
    assert _field_default(infrared_entity_field("infrared.missing", available)) is None
    assert (
        _field_default(
            infrared_entity_field_with_current(
                "infrared.missing",
                available,
            )
        )
        == "infrared.missing"
    )


def test_normalize_ids_and_command_names() -> None:
    """Test id and command normalization."""
    assert normalize_remote_id(" Living Room TV! ") == "living_room_tv"
    assert normalize_remote_id("!!!") == "remote"
    assert normalize_command_name(" power on! ") == "POWER_ON"


def test_unique_remote_id() -> None:
    """Test remote id collision handling."""
    remotes = [
        {CONF_REMOTE_ID: "living_room_tv"},
        {CONF_REMOTE_ID: "living_room_tv_2"},
    ]

    assert unique_remote_id("Living Room TV", remotes) == "living_room_tv_3"
    assert (
        unique_remote_id(
            "Living Room TV",
            remotes,
            current_remote_id="living_room_tv",
        )
        == "living_room_tv"
    )


def test_find_command_key_case_insensitive() -> None:
    """Test command key lookup."""
    commands = {"Power_On": "payload"}

    assert find_command_key(commands, "POWER_ON") == "Power_On"
    assert find_command_key(commands, "MISSING") is None


def test_normalize_virtual_remotes() -> None:
    """Test stored option normalization."""
    value: list[object] = [
        {
            CONF_REMOTE_ID: "valid",
            CONF_REMOTE_NAME: "Valid",
            CONF_INFRARED_ENTITY_ID: "infrared.valid",
            CONF_REMOTE_COMMANDS: {"POWER": "payload", "BAD": 1},
            "extra": "ignored",
        },
        {
            CONF_REMOTE_ID: "valid",
            CONF_REMOTE_NAME: "Duplicate",
            CONF_INFRARED_ENTITY_ID: "infrared.dup",
        },
        {
            CONF_REMOTE_ID: "",
            CONF_REMOTE_NAME: "Invalid",
            CONF_INFRARED_ENTITY_ID: "infrared.invalid",
        },
        "invalid",
    ]

    assert normalize_virtual_remotes(value) == [
        {
            CONF_REMOTE_ID: "valid",
            CONF_REMOTE_NAME: "Valid",
            CONF_INFRARED_ENTITY_ID: "infrared.valid",
            CONF_REMOTE_COMMANDS: {"POWER": "payload"},
        }
    ]
    assert normalize_virtual_remotes("invalid") == []


def test_remote_and_command_options() -> None:
    """Test options helpers."""
    remotes: list[dict[str, object]] = [
        {
            CONF_REMOTE_ID: "one",
            CONF_REMOTE_NAME: "One",
            CONF_INFRARED_ENTITY_ID: "infrared.one",
        },
        {
            CONF_REMOTE_ID: "two",
            CONF_REMOTE_NAME: "Two",
            CONF_INFRARED_ENTITY_ID: "infrared.two",
            CONF_REMOTE_COMMANDS: {"B": "payload", "A": "payload"},
        },
    ]

    normalized_remotes = normalize_virtual_remotes(remotes)

    assert remote_options(normalized_remotes) == [
        {"value": "one", "label": "One"},
        {"value": "two", "label": "Two"},
    ]
    assert command_options({"B": "payload", "A": "payload"}) == [
        {"value": "A", "label": "A"},
        {"value": "B", "label": "B"},
    ]
    assert remotes_with_commands(normalized_remotes) == [normalized_remotes[1]]


def test_infrared_entity_field_omits_unavailable_default() -> None:
    """Test infrared field omits defaults that are not available."""
    field = infrared_entity_field(
        "infrared.missing",
        {
            "infrared.available": selector.SelectOptionDict(
                value="infrared.available",
                label="Available",
            )
        },
    )

    assert field.default is vol.UNDEFINED


def test_command_options_ignores_malformed_command_mapping() -> None:
    """Test command options ignores malformed command mappings."""
    assert command_options(cast(Mapping[str, Any], "not-a-mapping")) == []


def test_infrared_entity_field_without_default_uses_required_field() -> None:
    """Test infrared entity field has no default when no valid default is provided."""
    field = infrared_entity_field(
        "",
        {
            "infrared.available": selector.SelectOptionDict(
                value="infrared.available",
                label="Available",
            )
        },
    )

    assert field.default is vol.UNDEFINED


def test_infrared_entity_field_with_current_without_default_uses_required_field() -> (
    None
):
    """Test current infrared entity field has no default when no current value exists."""
    field = infrared_entity_field_with_current(
        "",
        {
            "infrared.available": selector.SelectOptionDict(
                value="infrared.available",
                label="Available",
            )
        },
    )

    assert field.default is vol.UNDEFINED


def test_virtual_remote_from_config_entry_data() -> None:
    """Test normalizing a single virtual remote from config entry data."""
    assert virtual_remote_from_config_entry_data(
        {
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "TV",
            CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
            CONF_REMOTE_COMMANDS: {"POWER_ON": "38000:1,2", 1: "bad"},
        }
    ) == {
        CONF_REMOTE_ID: "tv",
        CONF_REMOTE_NAME: "TV",
        CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
        CONF_REMOTE_COMMANDS: {"POWER_ON": "38000:1,2"},
    }


def test_virtual_remote_from_config_entry_data_rejects_malformed_data() -> None:
    """Test malformed single virtual remote config entry data is rejected."""
    assert (
        virtual_remote_from_config_entry_data(
            {
                CONF_REMOTE_ID: "tv",
                CONF_REMOTE_NAME: "",
                CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
            }
        )
        is None
    )


def test_virtual_remotes_from_config_entry_prefers_options_list() -> None:
    """Test config entry remote normalization prefers the current options list."""
    entry = MockConfigEntry(
        domain="virtual_remote",
        data={
            CONF_REMOTE_ID: "single",
            CONF_REMOTE_NAME: "Single",
            CONF_INFRARED_ENTITY_ID: "infrared.single",
        },
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "list",
                    CONF_REMOTE_NAME: "List",
                    CONF_INFRARED_ENTITY_ID: "infrared.list",
                }
            ]
        },
    )

    assert virtual_remotes_from_config_entry(entry) == [
        {
            CONF_REMOTE_ID: "list",
            CONF_REMOTE_NAME: "List",
            CONF_INFRARED_ENTITY_ID: "infrared.list",
        }
    ]


def test_virtual_remotes_from_config_entry_supports_single_entry_data() -> None:
    """Test config entry remote normalization supports one-remote entry data."""
    entry = MockConfigEntry(
        domain="virtual_remote",
        data={
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "TV",
            CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
        },
        options={CONF_REMOTE_COMMANDS: {"POWER_ON": "38000:1,2"}},
    )

    assert virtual_remotes_from_config_entry(entry) == [
        {
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "TV",
            CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
            CONF_REMOTE_COMMANDS: {"POWER_ON": "38000:1,2"},
        }
    ]


def test_virtual_remotes_from_config_entry_rejects_malformed_single_entry_data() -> (
    None
):
    """Test config entry remote normalization rejects malformed one-remote data."""
    entry = MockConfigEntry(
        domain="virtual_remote",
        data={
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "",
            CONF_INFRARED_ENTITY_ID: "infrared.test_ir",
        },
        options={},
    )

    assert virtual_remotes_from_config_entry(entry) == []


def test_virtual_remotes_from_config_entry_supports_data_list_storage() -> None:
    """Test config entry remote normalization supports legacy list in entry data."""
    entry = MockConfigEntry(
        domain="virtual_remote",
        data={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "data_remote",
                    CONF_REMOTE_NAME: "Data Remote",
                    CONF_INFRARED_ENTITY_ID: "infrared.data_ir",
                }
            ]
        },
        options={},
    )

    assert virtual_remotes_from_config_entry(entry) == [
        {
            CONF_REMOTE_ID: "data_remote",
            CONF_REMOTE_NAME: "Data Remote",
            CONF_INFRARED_ENTITY_ID: "infrared.data_ir",
        }
    ]
