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
    ("keywords", "path"),
    [
        ('scope="function"', "tests.test_bootstrap"),
        ('scope="class"', "tests.test_bootstrap"),
        ('scope="module"', "tests.test_bootstrap"),
        ('scope="package"', "tests.test_bootstrap"),
        ('scope="session", autouse=True', "tests.test_bootstrap"),
        ('scope="function"', "tests.components.conftest"),
        ('scope="class"', "tests.components.conftest"),
        ('scope="module"', "tests.components.conftest"),
        ('scope="package"', "tests.components.conftest"),
        ('scope="session", autouse=True', "tests.components.conftest"),
        (
            'scope="session", autouse=find_spec("zeroconf") is not None',
            "tests.components.conftest",
        ),
        ('scope="function"', "tests.components.pylint_tests.conftest"),
        ('scope="class"', "tests.components.pylint_tests.conftest"),
        ('scope="module"', "tests.components.pylint_tests.conftest"),
        ('scope="package"', "tests.components.pylint_tests.conftest"),
        ('scope="function"', "tests.components.pylint_test"),
        ('scope="class"', "tests.components.pylint_test"),
        ('scope="module"', "tests.components.pylint_test"),
    ],
)
def test_good_fixture(
    linter: UnittestLinter, decorator_checker: BaseChecker, keywords: str, path: str
) -> None:
    """Test good `@pytest.fixture` decorator."""
    code = f"""
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture({keywords})
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


@pytest.mark.parametrize(
    "path",
    [
        "tests.components.pylint_test",
        "tests.components.pylint_test.conftest",
        "tests.components.pylint_test.module",
    ],
)
def test_bad_fixture_session_scope(
    linter: UnittestLinter, decorator_checker: BaseChecker, path: str
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

    root_node = astroid.parse(code, path)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-pytest-fixture-decorator",
            line=10,
            node=root_node.body[2].decorators.nodes[0],
            args=("scope `session`", "use `package` or lower"),
            confidence=UNDEFINED,
            col_offset=1,
            end_line=10,
            end_col_offset=32,
        ),
    ):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "path",
    [
        "tests.components.pylint_test",
        "tests.components.pylint_test.module",
    ],
)
def test_bad_fixture_package_scope(
    linter: UnittestLinter, decorator_checker: BaseChecker, path: str
) -> None:
    """Test bad `@pytest.fixture` decorator."""
    code = """
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture(scope="package")
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-pytest-fixture-decorator",
            line=10,
            node=root_node.body[2].decorators.nodes[0],
            args=("scope `package`", "use `module` or lower"),
            confidence=UNDEFINED,
            col_offset=1,
            end_line=10,
            end_col_offset=32,
        ),
    ):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "keywords",
    [
        'scope="session"',
        'scope="session", autouse=False',
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        "tests.test_bootstrap",
        "tests.components.conftest",
    ],
)
def test_bad_fixture_autouse(
    linter: UnittestLinter, decorator_checker: BaseChecker, keywords: str, path: str
) -> None:
    """Test bad `@pytest.fixture` decorator."""
    code = f"""
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture({keywords})
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-pytest-fixture-decorator",
            line=10,
            node=root_node.body[2].decorators.nodes[0],
            args=("scope/autouse combination", "set `autouse=True` or reduce scope"),
            confidence=UNDEFINED,
            col_offset=1,
            end_line=10,
            end_col_offset=17 + len(keywords),
        ),
    ):
        walker.walk(root_node)
