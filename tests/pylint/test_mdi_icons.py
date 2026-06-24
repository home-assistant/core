"""Tests for the MDI icons checker."""

import json
from pathlib import Path

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.mdi_icons import MdiIconsChecker
from pylint_home_assistant.helpers.icons import clear_icons_cache
import pytest

from . import assert_no_messages


@pytest.fixture(name="mdi_checker")
def mdi_checker_fixture(linter: UnittestLinter) -> MdiIconsChecker:
    """Fixture to provide an MDI icons checker."""
    clear_icons_cache()
    checker = MdiIconsChecker(linter)
    checker.open()
    return checker


def _make_integration(tmp_path: Path, icons: dict | None = None) -> Path:
    """Create a fake integration with optional icons.json."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    if icons is not None:
        (integration_dir / "icons.json").write_text(json.dumps(icons))
    return integration_dir


# --- Python code tests ---


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            'icon="mdi:thermometer"',
            id="valid_icon",
        ),
        pytest.param(
            'icon="mdi:lightning-bolt"',
            id="valid_icon_with_hyphen",
        ),
        pytest.param(
            'ICON = "mdi:home"',
            id="valid_icon_constant",
        ),
        pytest.param(
            'device_class = "temperature"',
            id="non_mdi_string",
        ),
        pytest.param(
            'icon = "mdi:%s" % icon_name',
            id="percent_format_template",
        ),
        pytest.param(
            'icon = "mdi:{}".format(icon_name)',
            id="str_format_template",
        ),
        pytest.param(
            'icon = f"mdi:{icon_name}"',
            id="fstring_template",
        ),
        pytest.param(
            'icon = "mdi:fan-speed-" + suffix',
            id="partial_with_concatenation",
        ),
    ],
)
def test_python_no_warning(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
    code: str,
) -> None:
    """Test that valid MDI icons in Python code pass."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")
    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("icon", "code"),
    [
        pytest.param(
            "mdi:nonexistent-icon-name",
            'icon="mdi:nonexistent-icon-name"',
            id="nonexistent_icon",
        ),
        pytest.param(
            "mdi:typo-thremometer",
            'ICON = "mdi:typo-thremometer"',
            id="typo_in_icon",
        ),
        pytest.param(
            "mdi:bad_icon",
            'icon = "mdi:bad_icon"',
            id="underscore_in_name",
        ),
        pytest.param(
            "mdi:Bad-Icon",
            'icon = "mdi:Bad-Icon"',
            id="uppercase_in_name",
        ),
    ],
)
def test_python_invalid_icon_flagged(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
    icon: str,
    code: str,
) -> None:
    """Test that invalid MDI icons in Python code are flagged."""
    root_node = astroid.parse(code, "homeassistant.components.test_integration.sensor")
    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-mdi-icon-not-found"
    assert icon in messages[0].args[0]


def test_python_not_integration_ignored(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        'ICON = "mdi:nonexistent-icon"',
        "tests.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


# --- icons.json tests ---


def test_icons_json_valid(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
    tmp_path: Path,
) -> None:
    """Test that valid icons.json passes."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "entity": {
                "sensor": {
                    "temperature": {"default": "mdi:thermometer"},
                }
            },
            "services": {
                "my_service": {"service": "mdi:cog"},
            },
        },
    )

    root_node = astroid.parse(
        "DOMAIN = 'test_int'",
        "homeassistant.components.test_int.__init__",
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_icons_json_invalid_flagged(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
    tmp_path: Path,
) -> None:
    """Test that invalid icons in icons.json are flagged."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "entity": {
                "sensor": {
                    "temperature": {"default": "mdi:nonexistent-sensor-icon"},
                }
            },
        },
    )

    root_node = astroid.parse(
        "DOMAIN = 'test_int'",
        "homeassistant.components.test_int.__init__",
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-mdi-icon-json-not-found"
    assert "nonexistent-sensor-icon" in messages[0].args[0]


def test_icons_json_no_file_no_warning(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
    tmp_path: Path,
) -> None:
    """Test that missing icons.json doesn't cause warnings."""
    integration_dir = _make_integration(tmp_path)

    root_node = astroid.parse(
        "DOMAIN = 'test_int'",
        "homeassistant.components.test_int.__init__",
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_icons_json_nested_invalid_flagged(
    linter: UnittestLinter,
    mdi_checker: MdiIconsChecker,
    tmp_path: Path,
) -> None:
    """Test that deeply nested invalid icons are caught."""
    integration_dir = _make_integration(
        tmp_path,
        {
            "entity": {
                "light": {
                    "my_light": {
                        "state_attributes": {
                            "effect": {
                                "state": {
                                    "sparkle": "mdi:does-not-exist",
                                }
                            }
                        }
                    }
                }
            },
        },
    )

    root_node = astroid.parse(
        "DOMAIN = 'test_int'",
        "homeassistant.components.test_int.__init__",
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(mdi_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert "does-not-exist" in messages[0].args[0]
