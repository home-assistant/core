"""Tests for hassfest conditions."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.util.yaml.loader import parse_yaml
from script.hassfest import conditions
from script.hassfest.model import Config

from . import get_integration

CONDITION_DESCRIPTION_FILENAME = "conditions.yaml"
CONDITION_ICONS_FILENAME = "icons.json"
CONDITION_STRINGS_FILENAME = "strings.json"

CONDITION_DESCRIPTIONS = {
    "valid": {
        CONDITION_DESCRIPTION_FILENAME: """
            _:
              target:
                entity:
                  domain: light
              fields:
                after:
                  example: sunrise
                  selector:
                    select:
                      options:
                        - sunrise
                        - sunset
                after_offset:
                  selector:
                    time: null
        """,
        CONDITION_ICONS_FILENAME: {"conditions": {"_": {"condition": "mdi:flash"}}},
        CONDITION_STRINGS_FILENAME: {
            "conditions": {
                "_": {
                    "name": "Sun",
                    "description": "When the sun is above/below the horizon",
                    "description_configured": "When a the sun rises or sets.",
                    "fields": {
                        "after": {"name": "After event", "description": "The event."},
                        "after_offset": {
                            "name": "Offset",
                            "description": "The offset.",
                        },
                    },
                }
            }
        },
        "errors": [],
    },
    "yaml_missing_colon": {
        CONDITION_DESCRIPTION_FILENAME: """
            test:
              fields
                entity:
                  selector:
                    entity:
        """,
        "errors": ["Invalid conditions.yaml"],
    },
    "invalid_conditions_schema": {
        CONDITION_DESCRIPTION_FILENAME: """
            invalid_condition:
              fields:
                entity:
                  selector:
                    invalid_selector: null
        """,
        "errors": ["Unknown selector type invalid_selector"],
    },
    "missing_strings_and_icons": {
        CONDITION_DESCRIPTION_FILENAME: """
            sun:
              fields:
                after:
                  example: sunrise
                  selector:
                    select:
                      options:
                        - sunrise
                        - sunset
                      translation_key: after
                after_offset:
                  selector:
                    time: null
        """,
        CONDITION_ICONS_FILENAME: {"conditions": {}},
        CONDITION_STRINGS_FILENAME: {
            "conditions": {
                "sun": {
                    "fields": {
                        "after_offset": {},
                    },
                }
            }
        },
        "errors": [
            "has no icon",
            "has no name",
            "has no description",
            "field after with no name",
            "field after with no description",
            "field after with a selector with a translation key",
            "field after_offset with no name",
            "field after_offset with no description",
        ],
    },
}


@pytest.mark.usefixtures("mock_core_integration")
def test_validate(config: Config) -> None:
    """Test validate version with no key."""

    def _load_yaml(fname, secrets=None):
        domain, yaml_file = fname.split("/")
        assert yaml_file == CONDITION_DESCRIPTION_FILENAME

        condition_descriptions = CONDITION_DESCRIPTIONS[domain][yaml_file]
        with io.StringIO(condition_descriptions) as file:
            return parse_yaml(file)

    def _patched_path_read_text(path: Path):
        domain = path.parent.name
        filename = path.name

        return json.dumps(CONDITION_DESCRIPTIONS[domain][filename])

    integrations = {
        domain: get_integration(domain, config) for domain in CONDITION_DESCRIPTIONS
    }

    with (
        patch("script.hassfest.conditions.grep_dir", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", _patched_path_read_text),
        patch("annotatedyaml.loader.load_yaml", side_effect=_load_yaml),
    ):
        conditions.validate(integrations, config)

    assert not config.errors

    for domain, description in CONDITION_DESCRIPTIONS.items():
        assert len(integrations[domain].errors) == len(description["errors"]), (
            f"Domain '{domain}' has unexpected errors: {integrations[domain].errors}"
        )
        for error, expected_error in zip(
            integrations[domain].errors, description["errors"], strict=True
        ):
            assert expected_error in error.error
