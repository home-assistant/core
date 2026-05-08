"""Tests for pylint hass_no_direct_init_calls_in_tests plugin."""

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
        from homeassistant.components.foo import async_setup_entry

        async def test_thing(hass, entry):
            await async_setup_entry(hass, entry)
        """,
            "homeassistant.components.foo.test_init",
            id="not_a_test_module",
        ),
        pytest.param(
            """
        async def test_thing(hass, entry):
            await hass.config_entries.async_setup(entry.entry_id)
        """,
            "tests.components.foo.test_init",
            id="config_entries_async_setup",
        ),
        pytest.param(
            """
        async def test_thing(hass, entry):
            await hass.config_entries.async_unload(entry.entry_id)
        """,
            "tests.components.foo.test_init",
            id="config_entries_async_unload",
        ),
        pytest.param(
            """
        async def async_setup_entry(hass, entry):
            return True

        async def test_thing(hass, entry):
            await async_setup_entry(hass, entry)
        """,
            "tests.components.foo.test_init",
            id="locally_defined_function",
        ),
        pytest.param(
            """
        from unittest.mock import patch

        async def test_thing():
            with patch("homeassistant.components.foo.async_setup_entry"):
                pass
        """,
            "tests.components.foo.test_init",
            id="patch_string_argument",
        ),
        pytest.param(
            """
        from homeassistant.setup import async_setup_component

        async def test_thing(hass):
            await async_setup_component(hass, "foo", {})
        """,
            "tests.components.foo.test_init",
            id="async_setup_component",
        ),
        pytest.param(
            """
        from homeassistant.components.foo.sensor import async_setup

        async def test_thing(hass, entry, async_add_entities):
            await async_setup(hass, entry, async_add_entities)
        """,
            "tests.components.foo.test_sensor",
            id="async_setup_from_platform_direct_import",
        ),
        pytest.param(
            """
        from homeassistant.components.foo import sensor

        async def test_thing(hass, entry, async_add_entities):
            await sensor.async_setup(hass, entry, async_add_entities)
        """,
            "tests.components.foo.test_sensor",
            id="async_setup_from_platform_submodule_alias",
        ),
    ],
)
def test_no_direct_init_calls_in_tests_good(
    linter: UnittestLinter,
    no_direct_init_calls_in_tests_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(no_direct_init_calls_in_tests_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


# Patterns where the function is imported from the integration's __init__.py.
# These are flagged for all four function names (including async_setup).
_INIT_BAD_TEMPLATES = [
    pytest.param(
        """
    from homeassistant.components.foo import {fn}

    async def test_thing(hass, entry):
        await {fn}(hass, entry)
    """,
        id="from_init_direct_import",
    ),
    pytest.param(
        """
    from homeassistant.components import foo

    async def test_thing(hass, entry):
        await foo.{fn}(hass, entry)
    """,
        id="from_components_module_alias",
    ),
    pytest.param(
        """
    import homeassistant.components.foo as foo

    async def test_thing(hass, entry):
        await foo.{fn}(hass, entry)
    """,
        id="aliased_dotted_import",
    ),
]

# Patterns where the function is imported from a platform submodule.
# These are flagged only for the entry/unload/migrate functions (NOT
# async_setup, since platforms have their own unrelated async_setup callbacks).
_SUBMODULE_BAD_TEMPLATES = [
    pytest.param(
        """
    from homeassistant.components.foo.sensor import {fn}

    async def test_thing(hass, entry):
        await {fn}(hass, entry)
    """,
        id="from_platform_direct_import",
    ),
    pytest.param(
        """
    from homeassistant.components.foo import sensor

    async def test_thing(hass, entry):
        await sensor.{fn}(hass, entry)
    """,
        id="from_integration_submodule_alias",
    ),
]


@pytest.mark.parametrize(
    "function_name",
    [
        "async_setup",
        "async_setup_entry",
        "async_unload_entry",
        "async_migrate_entry",
    ],
)
@pytest.mark.parametrize("code_template", _INIT_BAD_TEMPLATES)
def test_no_direct_init_calls_in_tests_init_bad(
    linter: UnittestLinter,
    no_direct_init_calls_in_tests_checker: BaseChecker,
    code_template: str,
    function_name: str,
) -> None:
    """Bad test cases for imports from the integration's __init__.py."""
    code = code_template.format(fn=function_name)
    root_node = astroid.parse(code, "tests.components.foo.test_init")
    walker = ASTWalker(linter)
    walker.add_checker(no_direct_init_calls_in_tests_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-no-direct-init-calls-in-tests"


@pytest.mark.parametrize(
    "function_name",
    ["async_setup_entry", "async_unload_entry", "async_migrate_entry"],
)
@pytest.mark.parametrize("code_template", _SUBMODULE_BAD_TEMPLATES)
def test_no_direct_init_calls_in_tests_submodule_bad(
    linter: UnittestLinter,
    no_direct_init_calls_in_tests_checker: BaseChecker,
    code_template: str,
    function_name: str,
) -> None:
    """Bad test cases for imports from an integration submodule."""
    code = code_template.format(fn=function_name)
    root_node = astroid.parse(code, "tests.components.foo.test_init")
    walker = ASTWalker(linter)
    walker.add_checker(no_direct_init_calls_in_tests_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-no-direct-init-calls-in-tests"
