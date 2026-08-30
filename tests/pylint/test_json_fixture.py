"""Tests for the JSON fixture checker."""

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.json_fixture import HassJsonFixtureChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="json_fixture_checker")
def json_fixture_checker_fixture(
    linter: UnittestLinter,
) -> HassJsonFixtureChecker:
    """Fixture to provide a JSON fixture checker."""
    return HassJsonFixtureChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            "value = json.loads(load_fixture('data.json', 'my_integration'))",
            id="json_loads_load_fixture",
        ),
        pytest.param(
            "value = json_loads(load_fixture('data.json'))",
            id="json_loads_helper",
        ),
        pytest.param(
            "value = json_loads_object(load_fixture('data.json'))",
            id="json_loads_object",
        ),
        pytest.param(
            "value = json_loads_array(load_fixture_bytes('data.json'))",
            id="json_loads_array_bytes",
        ),
        pytest.param(
            "value = json.loads(await async_load_fixture(hass, 'data.json'))",
            id="json_loads_async_load_fixture",
        ),
    ],
)
def test_flagged(
    linter: UnittestLinter,
    json_fixture_checker: HassJsonFixtureChecker,
    code: str,
) -> None:
    """Test cases that should be flagged."""
    root_node = astroid.parse(code, "tests.components.my_integration.test_sensor")
    call_node = next(root_node.nodes_of_class(astroid.nodes.Call))

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-json-fixture",
            node=call_node,
            line=call_node.lineno,
            col_offset=call_node.col_offset,
            end_line=call_node.end_lineno,
            end_col_offset=call_node.end_col_offset,
        ),
    ):
        walk_checker(linter, json_fixture_checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            "value = load_json_object_fixture('data.json', 'my_integration')",
            id="json_object_fixture_helper",
        ),
        pytest.param(
            "value = json.loads(some_string)",
            id="json_loads_non_fixture",
        ),
        pytest.param(
            "value = json.dumps(load_fixture('data.json'))",
            id="json_dumps_load_fixture",
        ),
        pytest.param(
            "value = load_fixture('data.json')",
            id="load_fixture_only",
        ),
    ],
)
def test_not_flagged(
    linter: UnittestLinter,
    json_fixture_checker: HassJsonFixtureChecker,
    code: str,
) -> None:
    """Test cases that should not be flagged."""
    root_node = astroid.parse(code, "tests.components.my_integration.test_sensor")

    with assert_no_messages(linter):
        walk_checker(linter, json_fixture_checker, root_node)


def test_not_flagged_outside_test_module(
    linter: UnittestLinter,
    json_fixture_checker: HassJsonFixtureChecker,
) -> None:
    """Test that non-test modules are ignored."""
    root_node = astroid.parse(
        "value = json.loads(load_fixture('data.json'))",
        "homeassistant.components.my_integration.sensor",
    )

    with assert_no_messages(linter):
        walk_checker(linter, json_fixture_checker, root_node)


def test_not_flagged_in_tests_common(
    linter: UnittestLinter,
    json_fixture_checker: HassJsonFixtureChecker,
) -> None:
    """Test that the fixture helper definitions in tests.common are ignored."""
    root_node = astroid.parse(
        "value = json_loads_object(load_fixture('data.json'))",
        "tests.common",
    )

    with assert_no_messages(linter):
        walk_checker(linter, json_fixture_checker, root_node)
