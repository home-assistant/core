"""Test automation helpers."""

import pytest
import voluptuous as vol

from homeassistant.helpers.automation import (
    get_absolute_description_key,
    get_relative_description_key,
    move_options_fields_to_top_level,
    move_top_level_schema_fields_to_options,
)


@pytest.mark.parametrize(
    ("relative_key", "absolute_key"),
    [
        ("turned_on", "homeassistant.turned_on"),
        ("_", "homeassistant"),
        ("_state", "state"),
    ],
)
def test_absolute_description_key(relative_key: str, absolute_key: str) -> None:
    """Test absolute description key."""
    DOMAIN = "homeassistant"
    assert get_absolute_description_key(DOMAIN, relative_key) == absolute_key


@pytest.mark.parametrize(
    ("relative_key", "absolute_key"),
    [
        ("turned_on", "homeassistant.turned_on"),
        ("_", "homeassistant"),
        ("_state", "state"),
    ],
)
def test_relative_description_key(relative_key: str, absolute_key: str) -> None:
    """Test relative description key."""
    DOMAIN = "homeassistant"
    assert get_relative_description_key(DOMAIN, absolute_key) == relative_key


@pytest.mark.parametrize(
    ("config", "schema_dict", "expected_config"),
    [
        (
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
                "attribute": "state",
                "value_template": "{{ value_json.val }}",
                "extra_field": "extra_value",
            },
            {},
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
                "attribute": "state",
                "value_template": "{{ value_json.val }}",
                "extra_field": "extra_value",
                "options": {},
            },
        ),
        (
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
                "attribute": "state",
                "value_template": "{{ value_json.val }}",
                "extra_field": "extra_value",
            },
            {
                vol.Required("entity"): str,
                vol.Optional("from"): str,
                vol.Optional("to"): str,
                vol.Optional("for"): dict,
                vol.Optional("attribute"): str,
                vol.Optional("value_template"): str,
            },
            {
                "platform": "test",
                "extra_field": "extra_value",
                "options": {
                    "entity": "sensor.test",
                    "from": "open",
                    "to": "closed",
                    "for": {"hours": 1},
                    "attribute": "state",
                    "value_template": "{{ value_json.val }}",
                },
            },
        ),
    ],
)
async def test_move_schema_fields_to_options(
    config, schema_dict, expected_config
) -> None:
    """Test moving schema fields to options."""
    assert (
        move_top_level_schema_fields_to_options(config, schema_dict) == expected_config
    )


@pytest.mark.parametrize(
    ("config", "expected_config"),
    [
        (
            {
                "platform": "test",
                "options": {
                    "entity": "sensor.test",
                    "from": "open",
                    "to": "closed",
                    "for": {"hours": 1},
                },
            },
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
            },
        ),
        (
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
            },
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
            },
        ),
        (
            {
                "platform": "test",
                "options": 456,
            },
            {
                "platform": "test",
                "options": 456,
            },
        ),
        (
            {
                "platform": "test",
                "options": {
                    "entity": "sensor.test",
                },
                "extra_field": "extra_value",
            },
            {
                "platform": "test",
                "options": {
                    "entity": "sensor.test",
                },
                "extra_field": "extra_value",
            },
        ),
    ],
)
async def test_move_options_fields_to_top_level(config, expected_config) -> None:
    """Test moving options fields to top-level."""
    base_schema = vol.Schema({vol.Required("platform"): str})
    original_config = config.copy()
    assert move_options_fields_to_top_level(config, base_schema) == expected_config
    assert config == original_config  # Ensure original config is not modified
