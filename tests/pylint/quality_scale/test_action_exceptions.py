"""Tests for the action_exceptions quality scale checker."""

from pathlib import Path

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.quality_scale.action_exceptions import (
    ActionExceptionsChecker,
)
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="action_exceptions_checker")
def action_exceptions_checker_fixture(
    linter: UnittestLinter,
) -> ActionExceptionsChecker:
    """Fixture to provide an action exceptions checker."""
    clear_quality_scale_cache()
    return ActionExceptionsChecker(linter)


def _make_integration(tmp_path: Path, rules: dict | None) -> Path:
    """Create a fake integration directory with an optional quality_scale.yaml."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))
    return integration_dir


@pytest.mark.parametrize(
    ("platform", "rules"),
    [
        pytest.param(
            "switch",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="switch",
        ),
        pytest.param(
            "button",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="button",
        ),
        pytest.param(
            "light",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="light",
        ),
        pytest.param(
            "media_player",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="media_player",
        ),
    ],
)
def test_action_exceptions_exempt_fires(
    linter: UnittestLinter,
    action_exceptions_checker: ActionExceptionsChecker,
    tmp_path: Path,
    platform: str,
    rules: dict,
) -> None:
    """Warning when action-exceptions is exempt on a controllable platform."""
    integration_dir = _make_integration(tmp_path, rules)

    root_node = astroid.parse(
        "async def async_setup_entry(hass, entry, async_add_entities): pass\n",
        f"homeassistant.components.test_int.{platform}",
    )
    root_node.file = str(integration_dir / f"{platform}.py")

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-exceptions-exempt",
            node=root_node,
            args=(platform,),
            line=0,
            col_offset=0,
        ),
    ):
        walk_checker(linter, action_exceptions_checker, root_node)


@pytest.mark.parametrize(
    ("module_name", "rules"),
    [
        pytest.param(
            "homeassistant.components.test_int.switch",
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            "homeassistant.components.test_int.switch",
            {"action-exceptions": "done"},
            id="rule_done",
        ),
        pytest.param(
            "homeassistant.components.test_int.switch",
            {"action-exceptions": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_int.switch",
            {"some-other-rule": "done"},
            id="rule_absent",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="read_only_platform",
        ),
        pytest.param(
            "homeassistant.components.test_int.config_flow",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="not_a_platform_module",
        ),
        pytest.param(
            "homeassistant.components.test_int",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="init_module",
        ),
        pytest.param(
            "not_homeassistant.something.switch",
            {"action-exceptions": {"status": "exempt", "comment": "No actions"}},
            id="not_an_integration",
        ),
    ],
)
def test_action_exceptions_not_fired(
    linter: UnittestLinter,
    action_exceptions_checker: ActionExceptionsChecker,
    tmp_path: Path,
    module_name: str,
    rules: dict | None,
) -> None:
    """No warning when the rule is not exempt or the platform has no actions."""
    integration_dir = _make_integration(tmp_path, rules)

    root_node = astroid.parse(
        "async def async_setup_entry(hass, entry, async_add_entities): pass\n",
        module_name,
    )
    root_node.file = str(integration_dir / "switch.py")

    with assert_no_messages(linter):
        walk_checker(linter, action_exceptions_checker, root_node)
