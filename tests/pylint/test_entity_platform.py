"""Tests for pylint hass_entity_platform plugin."""

from pathlib import Path

import astroid
from pylint.checkers import BaseChecker
import pylint.testutils
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_adds_messages, assert_no_messages


def test_entity_platform_missing_all(
    linter: UnittestLinter, entity_platform_checker: BaseChecker, tmp_path: Path
) -> None:
    """Ensure an entity platform root without __all__ is reported."""
    root_node = astroid.parse(
        'DOMAIN = "light"\n',
        "homeassistant.components.light",
        str(tmp_path / "__init__.py"),
    )

    with assert_adds_messages(
        linter,
        pylint.testutils.MessageTest(
            msg_id="home-assistant-entity-platform-missing-all",
            node=root_node,
            args=("light",),
            line=0,
            col_offset=0,
        ),
    ):
        entity_platform_checker.visit_module(root_node)


@pytest.mark.parametrize(
    ("module_name", "code", "filename"),
    [
        pytest.param(
            "homeassistant.components.light",
            'DOMAIN = "light"\n__all__ = ["DOMAIN"]\n',
            "__init__.py",
            id="entity_platform_with_all",
        ),
        pytest.param(
            "homeassistant.components.light.const",
            'DOMAIN = "light"\n',
            "const.py",
            id="entity_platform_submodule",
        ),
        pytest.param(
            "homeassistant.components.hue",
            'DOMAIN = "hue"\n',
            "__init__.py",
            id="not_an_entity_platform",
        ),
        pytest.param(
            "homeassistant.components.hue.light",
            'DOMAIN = "hue"\n',
            "light.py",
            id="platform_module_of_other_integration",
        ),
    ],
)
def test_entity_platform_ok(
    linter: UnittestLinter,
    entity_platform_checker: BaseChecker,
    tmp_path: Path,
    module_name: str,
    code: str,
    filename: str,
) -> None:
    """Ensure modules that are not entity platform roots, or define __all__, pass."""
    root_node = astroid.parse(code, module_name, str(tmp_path / filename))

    with assert_no_messages(linter):
        entity_platform_checker.visit_module(root_node)
