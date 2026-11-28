"""Tests for hassfest icons."""

import json
from pathlib import Path
from typing import Any

from hassfest.model import Config, Integration
import pytest

from script.hassfest import icons

INTEGRATION_CATEGORY_STRINGS = {
    "integration_category": {
        "energy": {
            "name": "Energy",
            "description": "Solar panels, home batteries and energy meters.",
            "subcategory": {
                "meters_monitoring": {"name": "Meters & monitoring"},
            },
        },
        "pets": {
            "name": "Pets",
            "description": "Feeders, litter boxes and pet doors.",
        },
    },
}

INTEGRATION_CATEGORY_ICONS = {
    "integration_category": {
        "energy": {
            "default": "mdi:lightning-bolt",
            "subcategory": {
                "meters_monitoring": {"default": "mdi:meter-electric"},
            },
        },
        "pets": {"default": "mdi:paw"},
    },
}


def _write_integration(
    config: Config,
    path: Path,
    icon_data: dict[str, Any],
    strings: str = json.dumps(INTEGRATION_CATEGORY_STRINGS),
) -> Integration:
    """Write an integration with strings and icons, and return it."""
    path.mkdir()
    (path / "strings.json").write_text(strings)
    (path / "icons.json").write_text(json.dumps(icon_data))
    return Integration(
        path,
        _config=config,
        _manifest={
            "domain": path.name,
            "name": path.name,
            "documentation": "https://example.com",
            "codeowners": ["@awesome"],
            "integration_type": "system",
        },
    )


def test_integration_category_icons(config: Config, tmp_path: Path) -> None:
    """Test valid integration category icons pass."""
    integration = _write_integration(
        config, tmp_path / "homeassistant", INTEGRATION_CATEGORY_ICONS
    )

    icons.validate_icon_file(config, integration)

    assert integration.errors == []


def test_integration_category_icons_only_for_homeassistant(
    config: Config, tmp_path: Path
) -> None:
    """Test other integrations can't define integration category icons."""
    integration = _write_integration(
        config, tmp_path / "test_integration", INTEGRATION_CATEGORY_ICONS
    )

    icons.validate_icon_file(config, integration)

    assert len(integration.errors) == 1
    assert "integration_category" in integration.errors[0].error


@pytest.mark.parametrize(
    ("icon_data", "expected_errors"),
    [
        (
            {
                "integration_category": {
                    "energy": {"default": "mdi:lightning-bolt"},
                    "pets": {"default": "mdi:paw"},
                }
            },
            ["Integration category `energy.meters_monitoring` has no icon"],
        ),
        (
            {
                "integration_category": {
                    **INTEGRATION_CATEGORY_ICONS["integration_category"],
                    "finance": {"default": "mdi:finance"},
                }
            },
            ["Icon for unknown integration category `finance`"],
        ),
        (
            {
                "integration_category": {
                    "energy": {
                        "default": "mdi:lightning-bolt",
                        "subcategory": {
                            "meters_monitoring": {"default": "mdi:meter-electric"},
                            "ev_charging": {"default": "mdi:ev-station"},
                        },
                    },
                }
            },
            [
                "Integration category `pets` has no icon",
                "Icon for unknown integration category `energy.ev_charging`",
            ],
        ),
    ],
)
def test_integration_category_icons_mismatch(
    config: Config,
    tmp_path: Path,
    icon_data: dict[str, Any],
    expected_errors: list[str],
) -> None:
    """Test categories and icons have to match."""
    integration = _write_integration(config, tmp_path / "homeassistant", icon_data)

    icons.validate_icon_file(config, integration)

    assert [error.error for error in integration.errors] == expected_errors


@pytest.mark.parametrize(
    "integration_category",
    [
        {"energy": {}},
        {"energy": {"default": "lightning-bolt"}},
        {
            "energy": {
                "default": "mdi:lightning-bolt",
                "subcategory": {"meters_monitoring": {}},
            }
        },
    ],
)
def test_integration_category_icons_invalid(
    config: Config, tmp_path: Path, integration_category: dict[str, Any]
) -> None:
    """Test invalid integration category icons are rejected."""
    integration = _write_integration(
        config,
        tmp_path / "homeassistant",
        {"integration_category": integration_category},
    )

    icons.validate_icon_file(config, integration)

    assert len(integration.errors) == 1
    assert integration.errors[0].error.startswith("Invalid icons.json")


@pytest.mark.parametrize(
    "strings",
    [
        pytest.param("{", id="invalid_json"),
        pytest.param("[]", id="not_an_object"),
        pytest.param('{"integration_category": []}', id="categories_not_an_object"),
        pytest.param('{"integration_category": {"energy": null}}', id="category_null"),
        pytest.param(
            '{"integration_category": {"energy": {"subcategory": null}}}',
            id="subcategory_null",
        ),
    ],
)
def test_integration_category_icons_invalid_strings(
    config: Config, tmp_path: Path, strings: str
) -> None:
    """Test invalid strings skip the comparison, other plugins report them."""
    integration = _write_integration(
        config, tmp_path / "homeassistant", INTEGRATION_CATEGORY_ICONS, strings
    )

    icons.validate_icon_file(config, integration)

    assert integration.errors == []


INTEGRATION_CONNECTIVITY_STRINGS = {
    "integration_connectivity": {
        "cloud": {
            "name": "Cloud",
            "description": "Services on the internet, like a manufacturer's cloud.",
        },
        "zigbee": {
            "name": "Zigbee",
            "description": "Zigbee devices, through a Zigbee radio or a bridge.",
        },
    },
}

INTEGRATION_CONNECTIVITY_ICONS = {
    "integration_connectivity": {
        "cloud": {"default": "mdi:cloud"},
        "zigbee": {"default": "mdi:zigbee"},
    },
}


def test_integration_connectivity_icons(config: Config, tmp_path: Path) -> None:
    """Test valid connectivity icons pass."""
    integration = _write_integration(
        config,
        tmp_path / "homeassistant",
        INTEGRATION_CONNECTIVITY_ICONS,
        json.dumps(INTEGRATION_CONNECTIVITY_STRINGS),
    )

    icons.validate_icon_file(config, integration)

    assert integration.errors == []


def test_integration_connectivity_icons_only_for_homeassistant(
    config: Config, tmp_path: Path
) -> None:
    """Test other integrations can't define connectivity icons."""
    integration = _write_integration(
        config,
        tmp_path / "test_integration",
        INTEGRATION_CONNECTIVITY_ICONS,
        json.dumps(INTEGRATION_CONNECTIVITY_STRINGS),
    )

    icons.validate_icon_file(config, integration)

    assert len(integration.errors) == 1
    assert "integration_connectivity" in integration.errors[0].error


@pytest.mark.parametrize(
    ("icon_data", "expected_errors"),
    [
        (
            {"integration_connectivity": {"cloud": {"default": "mdi:cloud"}}},
            ["Connectivity `zigbee` has no icon"],
        ),
        (
            {
                "integration_connectivity": {
                    **INTEGRATION_CONNECTIVITY_ICONS["integration_connectivity"],
                    "x10": {"default": "mdi:power-plug"},
                }
            },
            ["Icon for unknown connectivity `x10`"],
        ),
    ],
)
def test_integration_connectivity_icons_mismatch(
    config: Config,
    tmp_path: Path,
    icon_data: dict[str, Any],
    expected_errors: list[str],
) -> None:
    """Test connectivity values and icons have to match."""
    integration = _write_integration(
        config,
        tmp_path / "homeassistant",
        icon_data,
        json.dumps(INTEGRATION_CONNECTIVITY_STRINGS),
    )

    icons.validate_icon_file(config, integration)

    assert [error.error for error in integration.errors] == expected_errors


@pytest.mark.parametrize(
    "integration_connectivity",
    [
        {"zigbee": {}},
        {"zigbee": {"default": "zigbee"}},
        {"Zigbee": {"default": "mdi:zigbee"}},
    ],
)
def test_integration_connectivity_icons_invalid(
    config: Config, tmp_path: Path, integration_connectivity: dict[str, Any]
) -> None:
    """Test invalid connectivity icons are rejected."""
    integration = _write_integration(
        config,
        tmp_path / "homeassistant",
        {"integration_connectivity": integration_connectivity},
        json.dumps(INTEGRATION_CONNECTIVITY_STRINGS),
    )

    icons.validate_icon_file(config, integration)

    assert len(integration.errors) == 1
    assert integration.errors[0].error.startswith("Invalid icons.json")


@pytest.mark.parametrize(
    "strings",
    [
        pytest.param("{", id="invalid_json"),
        pytest.param("[]", id="not_an_object"),
    ],
)
def test_integration_connectivity_icons_invalid_strings(
    config: Config, tmp_path: Path, strings: str
) -> None:
    """Test invalid strings skip the comparison, other plugins report them."""
    integration = _write_integration(
        config, tmp_path / "homeassistant", INTEGRATION_CONNECTIVITY_ICONS, strings
    )

    icons.validate_icon_file(config, integration)

    assert integration.errors == []
