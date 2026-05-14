"""Tests for the config entry unloading quality scale checker."""

from pathlib import Path

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.quality_scale.config_entry_unloading import (
    ConfigEntryUnloadingChecker,
)
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages


@pytest.fixture(name="unloading_checker")
def unloading_checker_fixture(linter: UnittestLinter) -> ConfigEntryUnloadingChecker:
    """Fixture to provide a config entry unloading checker."""
    clear_quality_scale_cache()
    return ConfigEntryUnloadingChecker(linter)


def _create_quality_scale(integration_dir: Path, rules: dict | None = None) -> None:
    """Create a quality_scale.yaml in the integration directory."""
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))


def _make_integration(tmp_path: Path) -> Path:
    """Create a fake integration directory under components/."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    return integration_dir


def test_unload_entry_present(
    linter: UnittestLinter,
    unloading_checker: ConfigEntryUnloadingChecker,
    tmp_path: Path,
) -> None:
    """No warning when async_unload_entry is defined and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"config-entry-unloading": "done"})

    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    pass

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
""",
        "homeassistant.components.test_int",
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(unloading_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_unload_entry_missing_fires(
    linter: UnittestLinter,
    unloading_checker: ConfigEntryUnloadingChecker,
    tmp_path: Path,
) -> None:
    """Warning when async_unload_entry is missing and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"config-entry-unloading": "done"})

    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    pass
""",
        "homeassistant.components.test_int",
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(unloading_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-missing-config-entry-unloading",
            node=root_node,
            line=0,
            col_offset=0,
        ),
    ):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("module_name", "rules"),
    [
        pytest.param(
            "homeassistant.components.test_int",
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            "homeassistant.components.test_int",
            {"config-entry-unloading": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_int",
            {"config-entry-unloading": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"config-entry-unloading": "done"},
            id="not_init_module",
        ),
        pytest.param(
            "not_homeassistant.something",
            {"config-entry-unloading": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_unload_entry_not_fired(
    linter: UnittestLinter,
    unloading_checker: ConfigEntryUnloadingChecker,
    tmp_path: Path,
    module_name: str,
    rules: dict | None,
) -> None:
    """No warning when rule is not done or module is not __init__."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, rules)

    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    pass
""",
        module_name,
    )
    root_node.file = str(integration_dir / "__init__.py")

    walker = ASTWalker(linter)
    walker.add_checker(unloading_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
