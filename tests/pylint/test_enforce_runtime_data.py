"""Tests for pylint hass_enforce_runtime_data plugin."""

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
        hass.data[DATA_KEY] = some_value
        """,
            "homeassistant.components.test",
            id="non_domain_key",
        ),
        pytest.param(
            """
        hass.data[DOMAIN] = some_value
        """,
            "some.other.module",
            id="outside_components",
        ),
        pytest.param(
            """
        hass.data[DOMAIN] = some_value
        """,
            "homeassistant.components.test.config_flow",
            id="config_flow",
        ),
        pytest.param(
            """
        hass.data[DOMAIN] = some_value
        """,
            "homeassistant.components.test.const",
            id="const",
        ),
        pytest.param(
            """
        hass.data[DOMAIN] = some_value
        """,
            "homeassistant.components.test.diagnostics",
            id="diagnostics",
        ),
        pytest.param(
            """
        hass.data[DOMAIN] = some_value
        """,
            "homeassistant.components.test.application_credentials",
            id="application_credentials",
        ),
        pytest.param(
            """
        async def async_unload_entry(hass, entry):
            hass.data[DOMAIN].pop(entry.entry_id)
        """,
            "homeassistant.components.test",
            id="async_unload_entry",
        ),
        pytest.param(
            """
        async def async_remove_entry(hass, entry):
            hass.data[DOMAIN].pop(entry.entry_id)
        """,
            "homeassistant.components.test",
            id="async_remove_entry",
        ),
        pytest.param(
            """
        async def async_migrate_entry(hass, entry):
            old = hass.data[DOMAIN]
        """,
            "homeassistant.components.test",
            id="async_migrate_entry",
        ),
        pytest.param(
            """
        del hass.data[DOMAIN]
        """,
            "homeassistant.components.test",
            id="del_hass_data",
        ),
        pytest.param(
            """
        hass.data[DOMAIN].pop(entry.entry_id)
        """,
            "homeassistant.components.test",
            id="pop_from_hass_data",
        ),
    ],
)
def test_enforce_runtime_data(
    linter: UnittestLinter,
    enforce_runtime_data_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_runtime_data_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        hass.data[DOMAIN] = some_value
        """,
            "homeassistant.components.test",
            id="init_hass_data_domain",
        ),
        pytest.param(
            """
        hass.data[DOMAIN][entry.entry_id] = some_value
        """,
            "homeassistant.components.test",
            id="init_hass_data_domain_nested",
        ),
        pytest.param(
            """
        value = hass.data[DOMAIN]
        """,
            "homeassistant.components.test.sensor",
            id="sensor_hass_data_domain",
        ),
        pytest.param(
            """
        value = self.hass.data[DOMAIN]
        """,
            "homeassistant.components.test.sensor",
            id="self_hass_data_domain",
        ),
        pytest.param(
            """
        async def async_setup_entry(hass, entry):
            hass.data[DOMAIN] = {}
        """,
            "homeassistant.components.test",
            id="async_setup_entry",
        ),
    ],
)
def test_enforce_runtime_data_bad(
    linter: UnittestLinter,
    enforce_runtime_data_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_runtime_data_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-use-runtime-data"
