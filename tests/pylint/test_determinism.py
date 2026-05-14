"""Tests for the test determinism checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.test_determinism import HassTestDeterminismChecker
import pytest

from . import assert_no_messages


@pytest.fixture(name="determinism_checker")
def determinism_checker_fixture(linter: UnittestLinter) -> HassTestDeterminismChecker:
    """Fixture to provide a test determinism checker."""
    return HassTestDeterminismChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    assert hass.state == "ready"
""",
            "tests.components.test_integration.test_init",
            id="no_branching",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if not hass:
        return
    assert hass.state == "ready"
""",
            "tests.components.test_integration.test_init",
            id="guard_clause_return",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if sys.platform == "win32":
        pytest.skip("Not supported on Windows")
    assert hass.state == "ready"
""",
            "tests.components.test_integration.test_init",
            id="guard_clause_pytest_skip",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if not hass:
        pytest.fail("hass is required")
    assert hass.state == "ready"
""",
            "tests.components.test_integration.test_init",
            id="guard_clause_pytest_fail",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if not hass:
        raise ValueError("hass is required")
    assert hass.state == "ready"
""",
            "tests.components.test_integration.test_init",
            id="guard_clause_raise",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if not hass:
        pytest.xfail("expected to fail")
    assert hass.state == "ready"
""",
            "tests.components.test_integration.test_init",
            id="guard_clause_pytest_xfail",
        ),
        pytest.param(
            """
def test_something(action_type: str) -> None:
    if action_type == "template":
        action = {"wait_template": "{{ true }}"}
    else:
        action = {"wait_for_trigger": {"platform": "state"}}
    run_action(action)
""",
            "tests.components.test_integration.test_init",
            id="condition_references_parameter",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if hass.config.language == "en":
        data = {"lang": "en"}
    else:
        data = {"lang": "other"}
    do_something(data)
""",
            "tests.components.test_integration.test_init",
            id="if_without_assert_setup_only",
        ),
        pytest.param(
            """
@pytest.fixture
def my_fixture() -> None:
    if something:
        do_setup()
    else:
        do_other_setup()
""",
            "tests.components.test_integration.test_init",
            id="fixture_function_ignored",
        ),
        pytest.param(
            """
def helper_function() -> None:
    if something:
        do_a()
    else:
        do_b()
""",
            "tests.components.test_integration.test_init",
            id="non_test_function_ignored",
        ),
        pytest.param(
            """
def test_something(hass: HomeAssistant) -> None:
    if something:
        do_a()
    else:
        do_b()
""",
            "homeassistant.components.test_integration",
            id="not_test_module_ignored",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    determinism_checker: HassTestDeterminismChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(determinism_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_if_statement_flagged(
    linter: UnittestLinter,
    determinism_checker: HassTestDeterminismChecker,
) -> None:
    """Test that if statement with branching assertions is flagged."""
    root_node = astroid.parse(
        """
def test_sensor_value(hass) -> None:
    state = hass.states.get("sensor.test")
    if state.attributes.get("device_class") == "temperature":
        assert state.attributes.get("unit") == "C"
    else:
        assert state.attributes.get("unit") == "ppm"
""",
        "tests.components.test_integration.test_sensor",
    )
    walker = ASTWalker(linter)
    walker.add_checker(determinism_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-test-non-deterministic"
    assert messages[0].args == ("test_sensor_value", "if")


def test_multiple_if_statements(
    linter: UnittestLinter,
    determinism_checker: HassTestDeterminismChecker,
) -> None:
    """Test that multiple if statements are each flagged."""
    root_node = astroid.parse(
        """
def test_something(hass) -> None:
    if condition_a:
        assert do_a()

    if condition_b:
        assert do_b()
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(determinism_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 2


def test_async_test_function(
    linter: UnittestLinter,
    determinism_checker: HassTestDeterminismChecker,
) -> None:
    """Test that async test functions are also checked."""
    root_node = astroid.parse(
        """
async def test_something(hass) -> None:
    if something:
        assert do_a()
    else:
        assert do_b()
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(determinism_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("test_something", "if")


def test_match_statement_flagged(
    linter: UnittestLinter,
    determinism_checker: HassTestDeterminismChecker,
) -> None:
    """Test that match statements are also flagged."""
    root_node = astroid.parse(
        """
def test_something(state) -> None:
    match state:
        case "on":
            assert True
        case "off":
            assert False
""",
        "tests.components.test_integration.test_init",
    )
    walker = ASTWalker(linter)
    walker.add_checker(determinism_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].args == ("test_something", "match")
