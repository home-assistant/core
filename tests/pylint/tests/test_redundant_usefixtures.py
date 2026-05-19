"""Tests for the redundant usefixtures checker."""

from pathlib import Path

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.tests.redundant_usefixtures import (
    RedundantUsefixtures,
)
import pytest

from tests.pylint import assert_no_messages


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
pytestmark = pytest.mark.usefixtures("init_integration")

async def test_something(hass: HomeAssistant) -> None:
    pass
""",
            id="no_per_test_decorator",
        ),
        pytest.param(
            """
pytestmark = pytest.mark.usefixtures("init_integration")

@pytest.mark.usefixtures("other_fixture")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
            id="different_fixture",
        ),
        pytest.param(
            """
@pytest.mark.usefixtures("init_integration")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
            id="no_pytestmark",
        ),
        pytest.param(
            """
pytestmark = pytest.mark.parametrize("x", [1, 2])

@pytest.mark.usefixtures("init_integration")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
            id="pytestmark_not_usefixtures",
        ),
        pytest.param(
            """
pytestmark = pytest.mark.usefixtures("fixture_a")
pytestmark = pytest.mark.usefixtures("fixture_b")

@pytest.mark.usefixtures("fixture_a")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
            id="reassigned_pytestmark_only_last_active",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "tests.components.test_integration.test_init")
    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_single_fixture_redundant(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
) -> None:
    """Test that a redundant single-fixture decorator is flagged."""
    root_node = astroid.parse(
        """
pytestmark = pytest.mark.usefixtures("init_integration")

@pytest.mark.usefixtures("init_integration")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-tests-redundant-usefixtures"
    assert messages[0].args == ("init_integration",)


def test_multi_fixture_partial_redundant(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
) -> None:
    """Test that only the redundant fixture is flagged in a multi-fixture decorator."""
    root_node = astroid.parse(
        """
pytestmark = pytest.mark.usefixtures("init_integration")

@pytest.mark.usefixtures("init_integration", "other_fixture")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("init_integration",)


def test_pytestmark_list(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
) -> None:
    """Test that pytestmark as a list is handled."""
    root_node = astroid.parse(
        """
pytestmark = [pytest.mark.usefixtures("init_integration")]

@pytest.mark.usefixtures("init_integration")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_multiple_tests_flagged(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
) -> None:
    """Test that multiple tests with redundant decorators are each flagged."""
    root_node = astroid.parse(
        """
pytestmark = pytest.mark.usefixtures("mock_setup_entry")

@pytest.mark.usefixtures("mock_setup_entry")
async def test_a(hass: HomeAssistant) -> None:
    pass

@pytest.mark.usefixtures("mock_setup_entry")
async def test_b(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2


def test_conftest_pytestmark_redundant(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
    tmp_path: Path,
) -> None:
    """Test that pytestmark from a parent conftest.py is detected."""
    test_dir = tmp_path / "tests" / "components" / "test_int"
    test_dir.mkdir(parents=True)

    (test_dir / "conftest.py").write_text(
        'import pytest\npytestmark = pytest.mark.usefixtures("init_integration")\n'
    )

    root_node = astroid.parse(
        """
@pytest.mark.usefixtures("init_integration")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_int.test_init",
    )
    root_node.file = str(test_dir / "test_init.py")

    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("init_integration",)


def test_conftest_autouse_fixture_redundant(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
    tmp_path: Path,
) -> None:
    """Test that autouse fixtures from conftest.py are detected."""
    test_dir = tmp_path / "tests" / "components" / "test_int"
    test_dir.mkdir(parents=True)

    (test_dir / "conftest.py").write_text(
        "import pytest\n\n@pytest.fixture(autouse=True)\n"
        "def mock_setup_entry():\n    yield\n"
    )

    root_node = astroid.parse(
        """
@pytest.mark.usefixtures("mock_setup_entry")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_int.test_init",
    )
    root_node.file = str(test_dir / "test_init.py")

    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("mock_setup_entry",)


def test_conftest_autouse_named_fixture_redundant(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
    tmp_path: Path,
) -> None:
    """Test autouse fixtures with name= override detection."""
    test_dir = tmp_path / "tests" / "components" / "test_int"
    test_dir.mkdir(parents=True)

    (test_dir / "conftest.py").write_text(
        'import pytest\n\n@pytest.fixture(name="mock_setup_entry", autouse=True)\n'
        "def mock_setup_entry_fixture():\n    yield\n"
    )

    root_node = astroid.parse(
        """
@pytest.mark.usefixtures("mock_setup_entry")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "tests.components.test_int.test_init",
    )
    root_node.file = str(test_dir / "test_init.py")

    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("mock_setup_entry",)


def test_not_test_module_ignored(
    linter: UnittestLinter,
    usefixtures_checker: RedundantUsefixtures,
) -> None:
    """Test that non-test modules are ignored."""
    root_node = astroid.parse(
        """
pytestmark = pytest.mark.usefixtures("init_integration")

@pytest.mark.usefixtures("init_integration")
async def test_something(hass: HomeAssistant) -> None:
    pass
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(usefixtures_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
