"""Tests for the uncalled mock assertion checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.tests.uncalled_mock_assert import UncalledMockAssert
import pytest

from tests.pylint import assert_no_messages, walk_checker

MOCK_ASSERT_METHODS = (
    "assert_any_await",
    "assert_any_call",
    "assert_awaited",
    "assert_awaited_once",
    "assert_awaited_once_with",
    "assert_awaited_with",
    "assert_called",
    "assert_called_once",
    "assert_called_once_with",
    "assert_called_with",
    "assert_has_awaits",
    "assert_has_calls",
    "assert_not_awaited",
    "assert_not_called",
)


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> UncalledMockAssert:
    """Fixture to provide an uncalled mock assertion checker."""
    return UncalledMockAssert(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
def test_mock(mock_client):
    assert mock_client.assert_called_once()
""",
            "tests.components.sun.test_sensor",
            id="called",
        ),
        pytest.param(
            """
def test_mock(mock_client):
    mock_client.assert_called_once()
""",
            "tests.components.sun.test_sensor",
            id="statement",
        ),
        pytest.param(
            """
def test_mock(mock_client):
    assert mock_client.called
""",
            "tests.components.sun.test_sensor",
            id="called_attribute",
        ),
        pytest.param(
            """
def test_mock(mock_client):
    assert mock_client.call_count == 1
""",
            "tests.components.sun.test_sensor",
            id="call_count",
        ),
        pytest.param(
            """
def test_mock(client):
    assert client.assert_called_once_frobbed
""",
            "tests.components.sun.test_sensor",
            id="similar_name",
        ),
        pytest.param(
            """
def check(mock_client):
    assert mock_client.assert_called_once
""",
            "homeassistant.components.sun.sensor",
            id="not_a_test_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: UncalledMockAssert,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        *(
            pytest.param(
                f"""
def test_mock(mock_client):
    assert mock_client.{method}
""",
                [method],
                id=method,
            )
            for method in MOCK_ASSERT_METHODS
        ),
        pytest.param(
            """
def test_mock(mock_client):
    assert not mock_client.assert_not_called
""",
            ["assert_not_called"],
            id="negated",
        ),
        pytest.param(
            """
def test_mock(mock_client):
    assert mock_client.api.get_data.assert_awaited_once
""",
            ["assert_awaited_once"],
            id="nested_attribute",
        ),
        pytest.param(
            """
def test_mock(mock_client, mock_other):
    assert mock_client.assert_called_once and mock_other.assert_not_called
""",
            ["assert_called_once", "assert_not_called"],
            id="bool_op",
        ),
        pytest.param(
            """
def test_mock(mock_client):
    assert mock_client.called or not mock_client.assert_any_call
""",
            ["assert_any_call"],
            id="bool_op_negated",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: UncalledMockAssert,
    code: str,
    expected: list[str],
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, "tests.components.sun.test_sensor")
    walk_checker(linter, checker, root_node)

    messages = linter.release_messages()
    assert [message.msg_id for message in messages] == [
        "home-assistant-tests-uncalled-mock-assert"
    ] * len(expected)
    assert [message.args for message in messages] == [(method,) for method in expected]
