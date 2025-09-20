"""Tests for hassfest triggers."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.util.yaml.loader import parse_yaml
from script.hassfest import triggers
from script.hassfest.model import Config

from . import get_integration

TRIGGER_DESCRIPTION_FILENAME = "triggers.yaml"
TRIGGER_ICONS_FILENAME = "icons.json"
TRIGGER_STRINGS_FILENAME = "strings.json"

TRIGGER_DESCRIPTIONS = {
    "valid": {
        TRIGGER_DESCRIPTION_FILENAME: """
            _:
              fields:
                event:
                  example: sunrise
                  selector:
                    select:
                      options:
                        - sunrise
                        - sunset
                offset:
                  selector:
                    time: null
        """,
        TRIGGER_ICONS_FILENAME: {"triggers": {"_": {"trigger": "mdi:flash"}}},
        TRIGGER_STRINGS_FILENAME: {
            "triggers": {
                "_": {
                    "name": "MQTT",
                    "description": "When a specific message is received on a given MQTT topic.",
                    "description_configured": "When an MQTT message has been received",
                    "fields": {
                        "event": {"name": "Event", "description": "The event."},
                        "offset": {"name": "Offset", "description": "The offset."},
                    },
                }
            }
        },
        "errors": [],
    },
    "yaml_missing_colon": {
        TRIGGER_DESCRIPTION_FILENAME: """
            test:
              fields
                entity:
                  selector:
                    entity:
        """,
        "errors": ["Invalid triggers.yaml"],
    },
    "invalid_triggers_schema": {
        TRIGGER_DESCRIPTION_FILENAME: """
            invalid_trigger:
              fields:
                entity:
                  selector:
                    invalid_selector: null
        """,
        "errors": ["Unknown selector type invalid_selector"],
    },
    "missing_strings_and_icons": {
        TRIGGER_DESCRIPTION_FILENAME: """
            sun:
              fields:
                event:
                  example: sunrise
                  selector:
                    select:
                      options:
                        - sunrise
                        - sunset
                      translation_key: event
                offset:
                  selector:
                    time: null
        """,
        TRIGGER_ICONS_FILENAME: {"triggers": {}},
        TRIGGER_STRINGS_FILENAME: {
            "triggers": {
                "sun": {
                    "fields": {
                        "offset": {},
                    },
                }
            }
        },
        "errors": [
            "has no icon",
            "has no name",
            "has no description",
            "field event with no name",
            "field event with no description",
            "field event with a selector with a translation key",
            "field offset with no name",
            "field offset with no description",
        ],
    },
}


@pytest.mark.usefixtures("mock_core_integration")
def test_validate(config: Config) -> None:
    """Test validate version with no key."""

    def _load_yaml(fname, secrets=None):
        domain, yaml_file = fname.split("/")
        assert yaml_file == TRIGGER_DESCRIPTION_FILENAME

        trigger_descriptions = TRIGGER_DESCRIPTIONS[domain][yaml_file]
        with io.StringIO(trigger_descriptions) as file:
            return parse_yaml(file)

    def _patched_path_read_text(path: Path):
        domain = path.parent.name
        filename = path.name

        return json.dumps(TRIGGER_DESCRIPTIONS[domain][filename])

    integrations = {
        domain: get_integration(domain, config) for domain in TRIGGER_DESCRIPTIONS
    }

    with (
        patch("script.hassfest.triggers.grep_dir", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", _patched_path_read_text),
        patch("annotatedyaml.loader.load_yaml", side_effect=_load_yaml),
    ):
        triggers.validate(integrations, config)

    assert not config.errors

    for domain, description in TRIGGER_DESCRIPTIONS.items():
        assert len(integrations[domain].errors) == len(description["errors"]), (
            f"Domain '{domain}' has unexpected errors: {integrations[domain].errors}"
        )
        for error, expected_error in zip(
            integrations[domain].errors, description["errors"], strict=True
        ):
            assert expected_error in error.error
