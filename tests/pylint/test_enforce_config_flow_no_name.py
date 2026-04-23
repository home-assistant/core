"""Tests for pylint hass_enforce_config_flow_no_name plugin."""

from __future__ import annotations

import json
from pathlib import Path

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_no_messages


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        vol.Required(CONF_HOST)
        """,
            "homeassistant.components.test.config_flow",
            id="non_name_field",
        ),
        pytest.param(
            """
        vol.Optional("password")
        """,
            "homeassistant.components.test.config_flow",
            id="non_name_string_field",
        ),
        pytest.param(
            """
        vol.Optional("name")
        """,
            "homeassistant.components.test.sensor",
            id="name_in_sensor_not_flagged",
        ),
        pytest.param(
            """
        vol.Optional(CONF_NAME)
        """,
            "some.other.module",
            id="outside_components",
        ),
        pytest.param(
            """
        vol.Optional("name")
        """,
            "homeassistant.components.test",
            id="name_in_init_not_flagged",
        ),
    ],
)
def test_enforce_config_flow_no_name(
    linter: UnittestLinter,
    enforce_config_flow_no_name_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_name_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        vol.Required(CONF_NAME)
        """,
            "homeassistant.components.test.config_flow",
            id="conf_name",
        ),
        pytest.param(
            """
        vol.Optional("name", default="My Device")
        """,
            "homeassistant.components.test.config_flow",
            id="string_name",
        ),
        pytest.param(
            """
        vol.Required("device_name")
        """,
            "homeassistant.components.test.config_flow",
            id="device_name",
        ),
        pytest.param(
            """
        vol.Optional(CONF_DEVICE_NAME)
        """,
            "homeassistant.components.test.config_flow",
            id="conf_device_name",
        ),
    ],
)
def test_enforce_config_flow_no_name_bad(
    linter: UnittestLinter,
    enforce_config_flow_no_name_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_name_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-config-flow-name-field"


def test_enforce_config_flow_no_name_subentry_flow(
    linter: UnittestLinter,
    enforce_config_flow_no_name_checker: BaseChecker,
) -> None:
    """Test that subentry flows are not flagged."""
    code = """
    class MySubentryFlowHandler(ConfigSubentryFlow):
        async def async_step_user(self, user_input=None):
            return self.async_show_form(
                data_schema=vol.Schema({
                    vol.Required(CONF_NAME): str,
                })
            )
    """
    root_node = astroid.parse(code, "homeassistant.components.test.config_flow")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_name_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_enforce_config_flow_no_name_helper_integration(
    linter: UnittestLinter,
    enforce_config_flow_no_name_checker: BaseChecker,
    tmp_path: Path,
) -> None:
    """Test that helper integrations are not flagged."""
    integration_dir = tmp_path / "homeassistant" / "components" / "my_helper"
    integration_dir.mkdir(parents=True)
    (integration_dir / "config_flow.py").touch()
    (integration_dir / "manifest.json").write_text(
        json.dumps({"domain": "my_helper", "integration_type": "helper"})
    )

    code = """
    vol.Required(CONF_NAME)
    """
    root_node = astroid.parse(code, "homeassistant.components.my_helper.config_flow")
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_name_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_enforce_config_flow_no_name_non_helper_integration(
    linter: UnittestLinter,
    enforce_config_flow_no_name_checker: BaseChecker,
    tmp_path: Path,
) -> None:
    """Test that non-helper integrations are flagged."""
    integration_dir = tmp_path / "homeassistant" / "components" / "my_device"
    integration_dir.mkdir(parents=True)
    (integration_dir / "config_flow.py").touch()
    (integration_dir / "manifest.json").write_text(json.dumps({"domain": "my_device"}))

    code = """
    vol.Required(CONF_NAME)
    """
    root_node = astroid.parse(code, "homeassistant.components.my_device.config_flow")
    root_node.file = str(integration_dir / "config_flow.py")

    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_name_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-config-flow-name-field"
