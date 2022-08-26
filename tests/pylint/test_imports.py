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
    ("module_name", "import_from"),
    [
        ("homeassistant.components.pylint_test.sensor", "homeassistant.const"),
        ("homeassistant.components.pylint_test.sensor", ".const"),
        ("homeassistant.components.pylint_test.sensor", "."),
        ("homeassistant.components.pylint_test.sensor", "..pylint_test"),
        ("homeassistant.components.pylint_test.api.hub", "homeassistant.const"),
        ("homeassistant.components.pylint_test.api.hub", "..const"),
        ("homeassistant.components.pylint_test.api.hub", ".."),
        ("homeassistant.components.pylint_test.api.hub", "...pylint_test"),
    ],
)
def test_good_import(
    linter: UnittestLinter,
    imports_checker: BaseChecker,
    module_name: str,
    import_from: str,
) -> None:
    """Ensure good imports pass through ok."""

    import_node = astroid.extract_node(
        f"from {import_from} import CONSTANT #@",
        module_name,
    )
    imports_checker.visit_module(import_node.parent)

    with assert_no_messages(linter):
        imports_checker.visit_importfrom(import_node)


@pytest.mark.parametrize(
    ("module_name", "import_from", "error_code"),
    [
        (
            "homeassistant.components.pylint_test.sensor",
            "homeassistant.components.pylint_test.const",
            "hass-relative-import",
        ),
        (
            "homeassistant.components.pylint_test.sensor",
            "..const",
            "hass-absolute-import",
        ),
        (
            "homeassistant.components.pylint_test.sensor",
            "...const",
            "hass-absolute-import",
        ),
        (
            "homeassistant.components.pylint_test.api.hub",
            "homeassistant.components.pylint_test.api.const",
            "hass-relative-import",
        ),
        (
            "homeassistant.components.pylint_test.api.hub",
            "...const",
            "hass-absolute-import",
        ),
    ],
)
def test_bad_import(
    linter: UnittestLinter,
    imports_checker: BaseChecker,
    module_name: str,
    import_from: str,
    error_code: str,
) -> None:
    """Ensure bad imports are rejected."""

    import_node = astroid.extract_node(
        f"from {import_from} import CONSTANT #@",
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
            end_col_offset=len(import_from) + 21,
        ),
    ):
        imports_checker.visit_importfrom(import_node)
