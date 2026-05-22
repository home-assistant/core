"""Tests for the reauthentication flow quality scale checker."""

from pathlib import Path

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.quality_scale.reauthentication_flow import (
    ReauthenticationFlowChecker,
)
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
import pytest
import yaml

from tests.pylint import assert_adds_messages, assert_no_messages


@pytest.fixture(name="reauth_checker")
def reauth_checker_fixture(linter: UnittestLinter) -> ReauthenticationFlowChecker:
    """Fixture to provide a reauthentication flow checker."""
    clear_quality_scale_cache()
    return ReauthenticationFlowChecker(linter)


def _create_quality_scale(integration_dir: Path, rules: dict | None = None) -> None:
    """Create a quality_scale.yaml in the integration directory."""
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))


def _make_integration(tmp_path: Path) -> Path:
    """Create a fake integration directory under components/."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    return integration_dir


def test_reauth_present(
    linter: UnittestLinter,
    reauth_checker: ReauthenticationFlowChecker,
    tmp_path: Path,
) -> None:
    """No warning when async_step_reauth is defined and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"reauthentication-flow": "done"})

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        return self.async_show_form(step_id="reauth_confirm")
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(reauth_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_reauth_missing_fires(
    linter: UnittestLinter,
    reauth_checker: ReauthenticationFlowChecker,
    tmp_path: Path,
) -> None:
    """Warning when async_step_reauth is missing and rule is done."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, {"reauthentication-flow": "done"})

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
""",
        "homeassistant.components.test_int.config_flow",
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(reauth_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-missing-reauthentication-flow",
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
            "homeassistant.components.test_int.config_flow",
            None,
            id="no_quality_scale_file",
        ),
        pytest.param(
            "homeassistant.components.test_int.config_flow",
            {"reauthentication-flow": "todo"},
            id="rule_todo",
        ),
        pytest.param(
            "homeassistant.components.test_int.config_flow",
            {"reauthentication-flow": {"status": "exempt", "comment": "No auth"}},
            id="rule_exempt",
        ),
        pytest.param(
            "homeassistant.components.test_int.sensor",
            {"reauthentication-flow": "done"},
            id="not_config_flow_module",
        ),
        pytest.param(
            "not_homeassistant.something.config_flow",
            {"reauthentication-flow": "done"},
            id="not_an_integration",
        ),
    ],
)
def test_reauth_not_fired(
    linter: UnittestLinter,
    reauth_checker: ReauthenticationFlowChecker,
    tmp_path: Path,
    module_name: str,
    rules: dict | None,
) -> None:
    """No warning when rule is not done or module is not config_flow."""
    integration_dir = _make_integration(tmp_path)
    _create_quality_scale(integration_dir, rules)

    root_node = astroid.parse(
        """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
""",
        module_name,
    )
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(reauth_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
