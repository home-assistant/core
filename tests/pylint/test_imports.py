"""Tests for pylint hass_imports plugin."""
# pylint:disable=protected-access
from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
import pylint.testutils
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_adds_messages, assert_no_messages


@pytest.mark.parametrize(
    ("module_name", "import_from", "import_what"),
    [
        (
            "homeassistant.components.pylint_test.sensor",
            "homeassistant.const",
            "CONSTANT",
        ),
        ("homeassistant.components.pylint_test.sensor", ".const", "CONSTANT"),
        ("homeassistant.components.pylint_test.sensor", ".", "CONSTANT"),
        ("homeassistant.components.pylint_test.sensor", "..", "pylint_test"),
        (
            "homeassistant.components.pylint_test.api.hub",
            "homeassistant.const",
            "CONSTANT",
        ),
        ("homeassistant.components.pylint_test.api.hub", "..const", "CONSTANT"),
        ("homeassistant.components.pylint_test.api.hub", "..", "CONSTANT"),
        ("homeassistant.components.pylint_test.api.hub", "...", "pylint_test"),
    ],
)
def test_good_import(
    linter: UnittestLinter,
    imports_checker: BaseChecker,
    module_name: str,
    import_from: str,
    import_what: str,
) -> None:
    """Ensure good imports pass through ok."""

    import_node = astroid.extract_node(
        f"from {import_from} import {import_what} #@",
        module_name,
    )
    imports_checker.visit_module(import_node.parent)

    with assert_no_messages(linter):
        imports_checker.visit_importfrom(import_node)


@pytest.mark.parametrize(
    ("module_name", "import_from", "import_what", "error_code"),
    [
        (
            "homeassistant.components.pylint_test.sensor",
            "homeassistant.components.pylint_test.const",
            "CONSTANT",
            "hass-relative-import",
        ),
        (
            "homeassistant.components.pylint_test.sensor",
            "..const",
            "CONSTANT",
            "hass-absolute-import",
        ),
        (
            "homeassistant.components.pylint_test.sensor",
            "...const",
            "CONSTANT",
            "hass-absolute-import",
        ),
        (
            "homeassistant.components.pylint_test.api.hub",
            "homeassistant.components.pylint_test.api.const",
            "CONSTANT",
            "hass-relative-import",
        ),
        (
            "homeassistant.components.pylint_test.api.hub",
            "...const",
            "CONSTANT",
            "hass-absolute-import",
        ),
        (
            "homeassistant.components.pylint_test.api.hub",
            "homeassistant.components",
            "pylint_test",
            "hass-relative-import",
        ),
    ],
)
def test_bad_import(
    linter: UnittestLinter,
    imports_checker: BaseChecker,
    module_name: str,
    import_from: str,
    import_what: str,
    error_code: str,
) -> None:
    """Ensure bad imports are rejected."""

    import_node = astroid.extract_node(
        f"from {import_from} import {import_what} #@",
        module_name,
    )
    imports_checker.visit_module(import_node.parent)

    with assert_adds_messages(
        linter,
        pylint.testutils.MessageTest(
            msg_id=error_code,
            node=import_node,
            args=None,
            line=1,
            col_offset=0,
            end_line=1,
            end_col_offset=len(import_from) + len(import_what) + 13,
        ),
    ):
        imports_checker.visit_importfrom(import_node)
