"""Tests for hassfest integration connectivity."""

from dataclasses import replace
import json
from pathlib import Path

from hassfest.model import Config, Integration
import pytest

from script.hassfest import integration_connectivity

STRINGS = {
    "integration_connectivity": {
        "zigbee": {
            "name": "Zigbee",
            "description": "Zigbee devices, through a Zigbee radio or a bridge.",
        },
        "cloud": {
            "name": "Cloud",
            "description": "Services on the internet, like a manufacturer's cloud.",
        },
    },
}

ICONS = {
    "integration_connectivity": {
        "cloud": {"default": "mdi:cloud"},
        "zigbee": {"default": "mdi:zigbee"},
    },
}

EXPECTED = [
    {
        "slug": "cloud",
        "name": "Cloud",
        "description": "Services on the internet, like a manufacturer's cloud.",
        "icon": "mdi:cloud",
    },
    {
        "slug": "zigbee",
        "name": "Zigbee",
        "description": "Zigbee devices, through a Zigbee radio or a bridge.",
        "icon": "mdi:zigbee",
    },
]


@pytest.fixture
def integrations(config: Config, tmp_path: Path) -> dict[str, Integration]:
    """Return a homeassistant integration with connectivity strings and icons."""
    path = tmp_path / "homeassistant"
    path.mkdir()
    (path / "strings.json").write_text(json.dumps(STRINGS))
    (path / "icons.json").write_text(json.dumps(ICONS))
    return {"homeassistant": Integration(path, _config=config)}


@pytest.fixture
def root_config(config: Config, tmp_path: Path) -> Config:
    """Return a config rooted in a temporary directory."""
    (tmp_path / integration_connectivity.PATH).parent.mkdir(parents=True)
    return replace(config, root=tmp_path)


def test_generate(integrations: dict[str, Integration], root_config: Config) -> None:
    """Test the generated file is sorted and combines strings and icons."""
    integration_connectivity.validate(integrations, root_config)
    integration_connectivity.generate(integrations, root_config)

    path = root_config.root / integration_connectivity.PATH
    assert json.loads(path.read_text()) == EXPECTED

    root_config.errors.clear()
    integration_connectivity.validate(integrations, root_config)
    assert root_config.errors == []


def test_validate_missing_file(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test a missing file is a fixable error."""
    integration_connectivity.validate(integrations, root_config)

    assert len(root_config.errors) == 1
    assert root_config.errors[0].plugin == "integration_connectivity"
    assert root_config.errors[0].fixable


def test_validate_outdated_file(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test an outdated file is a fixable error."""
    (root_config.root / integration_connectivity.PATH).write_text("[]\n")

    integration_connectivity.validate(integrations, root_config)

    assert len(root_config.errors) == 1
    assert root_config.errors[0].plugin == "integration_connectivity"
    assert root_config.errors[0].fixable


def test_validate_skips_invalid_integration(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test invalid strings or icons are skipped, other plugins report them."""
    integration = integrations["homeassistant"]
    (integration.path / "strings.json").write_text("{")
    integration.add_error("json", "Invalid JSON in strings.json")

    integration_connectivity.validate(integrations, root_config)

    assert root_config.errors == []
    assert "integration_connectivity" not in root_config.cache


def test_generate_without_connectivity(
    integrations: dict[str, Integration], root_config: Config
) -> None:
    """Test strings and icons without connectivity generate an empty list."""
    integration = integrations["homeassistant"]
    (integration.path / "strings.json").write_text("{}")
    (integration.path / "icons.json").write_text("{}")

    integration_connectivity.validate(integrations, root_config)
    integration_connectivity.generate(integrations, root_config)

    path = root_config.root / integration_connectivity.PATH
    assert json.loads(path.read_text()) == []
