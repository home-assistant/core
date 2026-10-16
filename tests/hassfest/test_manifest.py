"""Tests for hassfest manifest validation."""

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pytest

from script.hassfest import manifest
from script.hassfest.model import Config, Integration

KNOWN_CATEGORIES = {
    "energy",
    "energy.ev_charging",
    "energy.meters_monitoring",
    "lighting",
    "lighting.bulbs_lamps",
    "plugs_switches",
}


def _validate(config: Config, manifest_extra: dict[str, Any]) -> list[str]:
    """Validate a core integration manifest and return the errors."""
    integration = Integration(
        Path("test"),
        _config=config,
        _manifest={
            "domain": "test",
            "name": "Test",
            "documentation": "https://www.home-assistant.io/integrations/test",
            "codeowners": ["@awesome"],
            "iot_class": "local_polling",
            **manifest_extra,
        },
    )
    manifest.validate_manifest(integration, Path("components"), KNOWN_CATEGORIES)
    return [error.error for error in integration.errors]


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    "categories",
    [
        pytest.param(["energy"], id="category"),
        pytest.param(["energy.ev_charging"], id="subcategory"),
        pytest.param(
            ["plugs_switches", "lighting.bulbs_lamps", "energy.meters_monitoring"],
            id="three",
        ),
    ],
)
def test_categories(config: Config, categories: list[str]) -> None:
    """Test valid categories pass."""
    assert _validate(config, {"categories": categories}) == []


@pytest.mark.usefixtures("mock_core_integration")
def test_no_categories(config: Config) -> None:
    """Test categories are optional."""
    assert _validate(config, {}) == []


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    "categories",
    [
        pytest.param([], id="empty"),
        pytest.param(
            ["energy", "lighting", "plugs_switches", "energy.ev_charging"],
            id="too_many",
        ),
        pytest.param(["energy", "energy"], id="duplicate"),
        pytest.param(["Energy"], id="uppercase"),
        pytest.param(["energy.ev_charging.fast"], id="too_deep"),
        pytest.param("energy", id="not_a_list"),
    ],
)
def test_invalid_categories(config: Config, categories: Any) -> None:
    """Test invalid categories are rejected by the schema."""
    errors = _validate(config, {"categories": categories})

    assert len(errors) == 1
    assert errors[0].startswith("Invalid manifest")


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    "category",
    [
        pytest.param("pets", id="category"),
        pytest.param("energy.backup_power", id="subcategory"),
    ],
)
def test_unknown_category(config: Config, category: str) -> None:
    """Test unknown categories are rejected."""
    assert _validate(config, {"categories": ["lighting", category]}) == [
        f"Unknown category `{category}`, see "
        "homeassistant/components/homeassistant/strings.json for the known categories"
    ]


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    "categories",
    [
        pytest.param(["energy", "energy.meters_monitoring"], id="parent_first"),
        pytest.param(["energy.meters_monitoring", "energy"], id="subcategory_first"),
    ],
)
def test_category_with_its_subcategory(config: Config, categories: list[str]) -> None:
    """Test a category can't be listed next to one of its own subcategories."""
    assert _validate(config, {"categories": categories}) == [
        "Category `energy` is implied by its subcategory "
        "`energy.meters_monitoring`, remove `energy`"
    ]


@pytest.mark.usefixtures("mock_core_integration")
def test_two_subcategories_of_one_category(config: Config) -> None:
    """Test two subcategories of the same category are fine."""
    assert (
        _validate(
            config,
            {"categories": ["energy.meters_monitoring", "energy.ev_charging"]},
        )
        == []
    )


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize("integration_type", ["entity", "system"])
def test_categories_not_allowed(config: Config, integration_type: str) -> None:
    """Test integration types people don't browse for can't have categories."""
    errors = _validate(
        config, {"integration_type": integration_type, "categories": ["energy"]}
    )

    assert errors == [f"Integrations of type {integration_type} can't have categories"]


@pytest.mark.usefixtures("mock_core_integration")
def test_categories_helper(config: Config) -> None:
    """Test helper integrations can have categories."""
    assert (
        _validate(config, {"integration_type": "helper", "categories": ["energy"]})
        == []
    )


@pytest.mark.usefixtures("mock_core_integration")
def test_categories_not_allowed_virtual(config: Config) -> None:
    """Test virtual integrations can't have categories."""
    integration = Integration(
        Path("test"),
        _config=config,
        _manifest={
            "domain": "test",
            "name": "Test",
            "integration_type": "virtual",
            "supported_by": "other",
            "categories": ["energy"],
        },
    )

    manifest.validate_manifest(integration, Path("components"), KNOWN_CATEGORIES)

    assert integration.errors[0].error.startswith("Invalid manifest")
    assert "categories" in integration.errors[0].error


def test_load_known_categories(config: Config) -> None:
    """Test the known categories come from the homeassistant strings."""
    known_categories = manifest.load_known_categories(config)

    assert known_categories is not None
    assert "energy" in known_categories
    assert "energy.ev_charging" in known_categories
    assert "diy_makers.serial_modbus" not in known_categories


def test_load_known_categories_before_generating(
    config: Config, tmp_path: Path
) -> None:
    """Test a new category is known before integration_categories.json exists."""
    strings_path = tmp_path / manifest.HOMEASSISTANT_STRINGS_PATH
    strings_path.parent.mkdir(parents=True)
    strings_path.write_text(
        json.dumps(
            {
                "integration_category": {
                    "pets": {
                        "name": "Pets",
                        "description": "Feeders and litter boxes.",
                        "subcategory": {"feeders": {"name": "Feeders"}},
                    }
                }
            }
        )
    )

    known_categories = manifest.load_known_categories(replace(config, root=tmp_path))

    assert known_categories == {"pets", "pets.feeders"}


@pytest.mark.parametrize(
    "strings",
    [
        pytest.param("{", id="invalid_json"),
        pytest.param("[]", id="not_an_object"),
        pytest.param('{"integration_category": {"pets": null}}', id="category_null"),
    ],
)
def test_load_known_categories_invalid_strings(
    config: Config, tmp_path: Path, strings: str
) -> None:
    """Test invalid strings skip the category check, other plugins report them."""
    strings_path = tmp_path / manifest.HOMEASSISTANT_STRINGS_PATH
    strings_path.parent.mkdir(parents=True)
    strings_path.write_text(strings)

    assert manifest.load_known_categories(replace(config, root=tmp_path)) is None


@pytest.mark.usefixtures("mock_core_integration")
def test_categories_skipped_without_known_categories(config: Config) -> None:
    """Test categories aren't checked when the known categories can't be loaded."""
    integration = Integration(
        Path("test"),
        _config=config,
        _manifest={
            "domain": "test",
            "name": "Test",
            "documentation": "https://www.home-assistant.io/integrations/test",
            "codeowners": ["@awesome"],
            "iot_class": "local_polling",
            "categories": ["pets"],
        },
    )

    manifest.validate_manifest(integration, Path("components"), None)

    assert integration.errors == []
