"""Tests for the flow start helpers checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.flow_start_helpers import FlowStartHelpersChecker
import pytest

from . import assert_no_messages, walk_checker

TEST_MODULE = "tests.components.test_integration.test_config_flow"


@pytest.fixture(name="flow_checker")
def flow_checker_fixture(linter: UnittestLinter) -> FlowStartHelpersChecker:
    """Fixture to provide a flow start helpers checker."""
    return FlowStartHelpersChecker(linter)


@pytest.mark.parametrize(
    ("code", "module"),
    [
        pytest.param(
            "result = await entry.start_reauth_flow(hass)",
            TEST_MODULE,
            id="helper",
        ),
        pytest.param(
            """
result = await hass.config_entries.flow.async_init(
    DOMAIN, context={"source": config_entries.SOURCE_USER}
)
""",
            TEST_MODULE,
            id="other_source",
        ),
        pytest.param(
            """
result = await hass.config_entries.flow.async_init(
    DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
)
""",
            "tests.common",
            id="outside_integration_tests",
        ),
        pytest.param(
            """
result = await hass.config_entries.flow.async_init(
    DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
)
""",
            "homeassistant.components.test_integration.config_flow",
            id="integration_code",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    flow_checker: FlowStartHelpersChecker,
    code: str,
    module: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module)

    with assert_no_messages(linter):
        walk_checker(linter, flow_checker, root_node)


@pytest.mark.parametrize(
    ("source", "helper"),
    [
        pytest.param(
            "config_entries.SOURCE_REAUTH", "start_reauth_flow", id="reauth_attr"
        ),
        pytest.param("SOURCE_REAUTH", "start_reauth_flow", id="reauth_name"),
        pytest.param('"reauth"', "start_reauth_flow", id="reauth_literal"),
        pytest.param(
            "config_entries.SOURCE_RECONFIGURE",
            "start_reconfigure_flow",
            id="reconfigure_attr",
        ),
        pytest.param(
            '"reconfigure"', "start_reconfigure_flow", id="reconfigure_literal"
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    flow_checker: FlowStartHelpersChecker,
    source: str,
    helper: str,
) -> None:
    """Test that manually started flows are flagged."""
    root_node = astroid.parse(
        f"""
result = await hass.config_entries.flow.async_init(
    DOMAIN,
    context={{"source": {source}, "entry_id": entry.entry_id}},
    data=entry.data,
)
""",
        TEST_MODULE,
    )
    walk_checker(linter, flow_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-test-flow-start-helper"
    assert messages[0].args == (helper,)
