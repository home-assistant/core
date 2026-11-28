"""Tests for hassfest integration categories."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from script.hassfest import integration_categories
from script.hassfest.model import Config, Integration

STRINGS = {
    "integration_category": {
        "pets": {
            "name": "Pets",
            "description": "Feeders, litter boxes and pet doors.",
        },
        "energy": {
            "name": "Energy",
            "description": "Solar panels, home batteries and energy meters.",
            "subcategory": {
                "meters_monitoring": {"name": "Meters & monitoring"},
                "ev_charging": {"name": "EV charging"},
            },
        },
    },
}

ICONS = {
    "integration_category": {
        "energy": {
            "default": "mdi:lightning-bolt",
            "subcategory": {
                "ev_charging": {"default": "mdi:ev-station"},
                "meters_monitoring": {"default": "mdi:meter-electric"},
            },
        },
        "pets": {"default": "mdi:paw"},
    },
}

EXPECTED = [
    {
        "slug": "energy",
        "name": "Energy",
        "description": "Solar panels, home batteries and energy meters.",
        "icon": "mdi:lightning-bolt",
        "subcategories": [
            {"slug": "ev_charging", "name": "EV charging", "icon": "mdi:ev-station"},
            {
                "slug": "meters_monitoring",
                "name": "Meters & monitoring",
                "icon": "mdi:meter-electric",
            },
        ],
    },
    {
        "slug": "pets",
        "name": "Pets",
        "description": "Feeders, litter boxes and pet doors.",
        "icon": "mdi:paw",
        "subcategories": [],
    },
]


@pytest.fixture
def integrations(config: Config, tmp_path: Path) -> dict[str, Integration]:
    """Return a homeassistant integration with category strings and icons."""
    path = tmp_path / "homeassistant"
    path.mkdir()
    (path / "strings.json").write_text(json.dumps(STRINGS))
    (path / "icons.json").write_text(json.dumps(ICONS))
    return {"homeassistant": Integration(path, _config=config)}


@pytest.fixture
def root_config(config: Config, tmp_path: Path) -> Config:
    """Return a config rooted in a temporary directory."""
    (tmp_path / integration_categories.PATH).parent.mkdir(parents=True)
    return replace(config, root=tmp_path)


def test_generate(integrations: dict[str, Integration], root_config: Config) -> None:
    """Test the generated file is sorted and combines strings and icons."""
    integration_categories.validate(integrations, root_config)
    integration_categories.generate(integrations, root_config)

    path = root_config.root / integration_categories.PATH
    assert json.loads(path.read_text()) == EXPECTED

    root_config.errors.clear()
    integration_categories.validate(integrations, root_config)
    assert root_config.errors == []


def test_validate_missing_file(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test a missing file is a fixable error."""
    integration_categories.validate(integrations, root_config)

    assert len(root_config.errors) == 1
    assert root_config.errors[0].plugin == "integration_categories"
    assert root_config.errors[0].fixable


def test_validate_outdated_file(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test an outdated file is a fixable error."""
    (root_config.root / integration_categories.PATH).write_text("[]\n")

    integration_categories.validate(integrations, root_config)

    assert len(root_config.errors) == 1
    assert root_config.errors[0].plugin == "integration_categories"
    assert root_config.errors[0].fixable


def test_validate_skips_invalid_integration(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test invalid strings or icons are skipped, other plugins report them."""
    integration = integrations["homeassistant"]
    (integration.path / "strings.json").write_text("{")
    integration.add_error("json", "Invalid JSON in strings.json")

    integration_categories.validate(integrations, root_config)

    assert root_config.errors == []
    assert "integration_categories" not in root_config.cache


def test_generate_without_categories(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test strings and icons without categories generate an empty list."""
    integration = integrations["homeassistant"]
    (integration.path / "strings.json").write_text("{}")
    (integration.path / "icons.json").write_text("{}")

    integration_categories.validate(integrations, root_config)
    integration_categories.generate(integrations, root_config)

    path = root_config.root / integration_categories.PATH
    assert json.loads(path.read_text()) == []
