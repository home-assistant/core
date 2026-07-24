"""Tests for pylint hass_enforce_runtime_data_type plugin."""

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
        from homeassistant.config_entries import ConfigEntry

        async def async_setup_entry(hass, entry: MyConfigEntry) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "homeassistant.components.test",
            id="typed_alias",
        ),
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        type MyConfigEntry = ConfigEntry[MyData]

        async def async_setup_entry(hass, entry: ConfigEntry[MyData]) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "homeassistant.components.test",
            id="subscripted_inline",
        ),
        pytest.param(
            """
        async def async_unload_entry(hass, entry) -> bool:
            del entry.runtime_data
            return True
        """,
            "homeassistant.components.test",
            id="no_annotation",
        ),
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
            entry.something_else = 1
            return True
        """,
            "homeassistant.components.test",
            id="not_runtime_data",
        ),
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "homeassistant.components.test.sensor",
            id="bare_config_entry_in_platform",
        ),
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "some.other.module",
            id="outside_components",
        ),
    ],
)
def test_enforce_runtime_data_type(
    linter: UnittestLinter,
    enforce_runtime_data_type_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_runtime_data_type_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "homeassistant.components.test",
            id="assign_runtime_data",
        ),
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
            value = entry.runtime_data
            return True
        """,
            "homeassistant.components.test",
            id="read_runtime_data",
        ),
        pytest.param(
            """
        from homeassistant import config_entries

        async def async_setup_entry(hass, entry: config_entries.ConfigEntry) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "homeassistant.components.test",
            id="qualified_config_entry",
        ),
        pytest.param(
            """
        from homeassistant.config_entries import ConfigEntry

        async def async_migrate_entry(hass, entry: ConfigEntry) -> bool:
            entry.runtime_data = MyData()
            return True
        """,
            "homeassistant.components.test",
            id="not_only_setup",
        ),
    ],
)
def test_enforce_runtime_data_type_bad(
    linter: UnittestLinter,
    enforce_runtime_data_type_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_runtime_data_type_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-runtime-data-needs-typed-config-entry"
