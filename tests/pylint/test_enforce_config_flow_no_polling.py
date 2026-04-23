"""Tests for pylint hass_enforce_config_flow_no_polling plugin."""

from __future__ import annotations

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
            id="non_polling_field",
        ),
        pytest.param(
            """
        vol.Optional("username")
        """,
            "homeassistant.components.test.config_flow",
            id="non_polling_string_field",
        ),
        pytest.param(
            """
        vol.Optional(CONF_SCAN_INTERVAL)
        """,
            "homeassistant.components.test.sensor",
            id="polling_in_sensor_not_flagged",
        ),
        pytest.param(
            """
        vol.Optional(CONF_SCAN_INTERVAL)
        """,
            "some.other.module",
            id="outside_components",
        ),
        pytest.param(
            """
        vol.Optional("scan_interval", default=30)
        """,
            "homeassistant.components.test",
            id="polling_in_init_not_flagged",
        ),
        pytest.param(
            """
        vol.Optional("check_interval")
        """,
            "homeassistant.components.test.config_flow",
            id="unknown_interval_field",
        ),
        pytest.param(
            """
        vol.Optional("poll_frequency")
        """,
            "homeassistant.components.test.config_flow",
            id="unknown_frequency_field",
        ),
    ],
)
def test_enforce_config_flow_no_polling(
    linter: UnittestLinter,
    enforce_config_flow_no_polling_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_polling_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        vol.Optional(CONF_SCAN_INTERVAL)
        """,
            "homeassistant.components.test.config_flow",
            id="conf_scan_interval",
        ),
        pytest.param(
            """
        vol.Optional("scan_interval", default=30)
        """,
            "homeassistant.components.test.config_flow",
            id="string_scan_interval",
        ),
        pytest.param(
            """
        vol.Required("update_interval")
        """,
            "homeassistant.components.test.config_flow",
            id="update_interval",
        ),
        pytest.param(
            """
        vol.Optional("update_frequency", default=60)
        """,
            "homeassistant.components.test.config_flow",
            id="update_frequency",
        ),
        pytest.param(
            """
        vol.Optional("refresh_interval")
        """,
            "homeassistant.components.test.config_flow",
            id="refresh_interval",
        ),
        pytest.param(
            """
        vol.Optional(CONF_UPDATE_INTERVAL)
        """,
            "homeassistant.components.test.config_flow",
            id="conf_update_interval",
        ),
    ],
)
def test_enforce_config_flow_no_polling_bad(
    linter: UnittestLinter,
    enforce_config_flow_no_polling_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_flow_no_polling_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-config-flow-polling-field"
