"""Tests for pylint hass_enforce_type_hints plugin."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_adds_messages, assert_no_messages


def test_good_callback(linter: UnittestLinter, decorator_checker: BaseChecker) -> None:
    """Test good `@callback` decorator."""
    code = """
    from homeassistant.core import callback

    @callback
    def setup(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_bad_callback(linter: UnittestLinter, decorator_checker: BaseChecker) -> None:
    """Test bad `@callback` decorator."""
    code = """
    from homeassistant.core import callback

    @callback
    async def setup(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-async-callback-decorator",
            line=5,
            node=root_node.body[1],
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=15,
        ),
    ):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("scope", "path"),
    [
        ("function", "tests.test_bootstrap"),
        ("class", "tests.test_bootstrap"),
        ("module", "tests.test_bootstrap"),
        ("package", "tests.test_bootstrap"),
        ("session", "tests.test_bootstrap"),
        ("function", "tests.components.conftest"),
        ("class", "tests.components.conftest"),
        ("module", "tests.components.conftest"),
        ("package", "tests.components.conftest"),
        ("session", "tests.components.conftest"),
        ("function", "tests.components.pylint_test"),
        ("class", "tests.components.pylint_test"),
        ("module", "tests.components.pylint_test"),
        ("package", "tests.components.pylint_test"),
    ],
)
def test_good_fixture(
    linter: UnittestLinter, decorator_checker: BaseChecker, scope: str, path: str
) -> None:
    """Test good `@pytest.fixture` decorator."""
    code = f"""
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture(scope="{scope}")
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_bad_fixture_scope(
    linter: UnittestLinter, decorator_checker: BaseChecker
) -> None:
    """Test bad `@pytest.fixture` decorator."""
    code = """
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture(scope="session")
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, "tests.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-pytest-fixture-decorator",
            line=11,
            node=root_node.body[2],
            args=("scope `session`", "`package` or lower"),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=11,
            end_col_offset=17,
        ),
    ):
        walker.walk(root_node)
