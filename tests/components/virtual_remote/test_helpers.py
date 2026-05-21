"""Tests for virtual remote helper functions."""

from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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
    available = {"infrared.valid": {"value": "infrared.valid", "label": "Valid"}}

    selector = infrared_entity_selector(
        available,
        current_entity_id="infrared.missing",
    )

    values = [option["value"] for option in selector.config["options"]]
    assert values == ["infrared.valid", "infrared.missing"]


def test_infrared_entity_field_defaults() -> None:
    """Test selector field defaults."""
    available = {"infrared.valid": {"value": "infrared.valid", "label": "Valid"}}

    assert (
        infrared_entity_field("infrared.valid", available).default() == "infrared.valid"
    )
    assert infrared_entity_field("infrared.missing", available).default() is None
    assert (
        infrared_entity_field_with_current(
            "infrared.missing",
            available,
        ).default()
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
    value = [
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
    remotes = [
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

    assert remote_options(remotes) == [
        {"value": "one", "label": "One"},
        {"value": "two", "label": "Two"},
    ]
    assert command_options({"B": "payload", "A": "payload"}) == [
        {"value": "A", "label": "A"},
        {"value": "B", "label": "B"},
    ]
    assert remotes_with_commands(remotes) == [remotes[1]]
