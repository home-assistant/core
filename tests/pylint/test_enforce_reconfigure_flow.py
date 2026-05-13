"""Tests for pylint hass_enforce_reconfigure_flow plugin."""

from pathlib import Path

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest
import yaml

from . import assert_no_messages


def _create_quality_scale(integration_dir: Path, rules: dict | None = None) -> None:
    """Create a quality_scale.yaml in the integration directory."""
    if rules is not None:
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump({"rules": rules}))


@pytest.mark.parametrize(
    ("code", "module_name", "rules"),
    [
        pytest.param(
            """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reconfigure(self, user_input=None):
        pass
        """,
            "homeassistant.components.test_int.config_flow",
            {"reconfigure-flow": "done"},
            id="has_reconfigure_step",
        ),
        pytest.param(
            """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
        """,
            "homeassistant.components.test_int.config_flow",
            None,
            id="no_quality_scale",
        ),
        pytest.param(
            """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
        """,
            "homeassistant.components.test_int.config_flow",
            {"reconfigure-flow": {"status": "exempt", "comment": "reason"}},
            id="rule_exempt",
        ),
        pytest.param(
            """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
        """,
            "homeassistant.components.test_int.config_flow",
            {"some-other-rule": "done"},
            id="rule_absent",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry):
    pass
        """,
            "homeassistant.components.test_int.sensor",
            {"reconfigure-flow": "done"},
            id="not_config_flow",
        ),
        pytest.param(
            """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
        """,
            "some.other.module.config_flow",
            None,
            id="outside_components",
        ),
    ],
)
def test_enforce_reconfigure_flow(
    linter: UnittestLinter,
    enforce_reconfigure_flow_checker: BaseChecker,
    tmp_path: Path,
    code: str,
    module_name: str,
    rules: dict | None,
) -> None:
    """Good test cases."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    config_flow_file = integration_dir / "config_flow.py"
    config_flow_file.touch()
    _create_quality_scale(integration_dir, rules)

    root_node = astroid.parse(code, module_name)
    root_node.file = str(config_flow_file)

    walker = ASTWalker(linter)
    walker.add_checker(enforce_reconfigure_flow_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_enforce_reconfigure_flow_bad(
    linter: UnittestLinter,
    enforce_reconfigure_flow_checker: BaseChecker,
    tmp_path: Path,
) -> None:
    """Bad test case: claims done but no async_step_reconfigure."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    config_flow_file = integration_dir / "config_flow.py"
    config_flow_file.touch()
    _create_quality_scale(integration_dir, {"reconfigure-flow": "done"})

    code = """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
    """
    root_node = astroid.parse(code, "homeassistant.components.test_int.config_flow")
    root_node.file = str(config_flow_file)

    walker = ASTWalker(linter)
    walker.add_checker(enforce_reconfigure_flow_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-reconfigure-flow-missing"


def test_enforce_reconfigure_flow_bad_status_done(
    linter: UnittestLinter,
    enforce_reconfigure_flow_checker: BaseChecker,
    tmp_path: Path,
) -> None:
    """Bad test case: rule is {status: done} dict form."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    config_flow_file = integration_dir / "config_flow.py"
    config_flow_file.touch()
    _create_quality_scale(
        integration_dir,
        {"reconfigure-flow": {"status": "done", "comment": "implemented"}},
    )

    code = """
class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        pass
    """
    root_node = astroid.parse(code, "homeassistant.components.test_int.config_flow")
    root_node.file = str(config_flow_file)

    walker = ASTWalker(linter)
    walker.add_checker(enforce_reconfigure_flow_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-reconfigure-flow-missing"
