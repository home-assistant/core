"""Tests for the config flow error recovery checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.config_flow_error_recovery import (
    ConfigFlowErrorRecovery,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_MODULE_NAME = "tests.components.test_integration.test_config_flow"

# A helper outside the integration's tests that would otherwise count
astroid.MANAGER.cache_module(
    astroid.parse(
        """
def assert_create_entry(result):
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
        "tests.flow_helpers",
    )
)


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> ConfigFlowErrorRecovery:
    """Fixture to provide a config flow error recovery checker."""
    return ConfigFlowErrorRecovery(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def test_form_errors(hass, mock_client, exception, error):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_client.connect.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            _MODULE_NAME,
            id="recovers",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"]["base"] == "cannot_connect"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") == "create_entry"
""",
            _MODULE_NAME,
            id="nested_errors_and_get",
        ),
        pytest.param(
            """
async def test_full_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["errors"] == {}
    assert result["errors"] == None
    assert result.get("errors") is None
    assert result["errors"] != {"base": "cannot_connect"}
    assert "base" not in result["errors"]
    if result["errors"]:
        pass
""",
            _MODULE_NAME,
            id="no_errors",
        ),
        pytest.param(
            """
async def test_reauth_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
""",
            _MODULE_NAME,
            id="reauth_successful",
        ),
        pytest.param(
            """
import pytest

@pytest.mark.parametrize(
    ("start_flow", "reason"),
    [
        (start_reauth, "reauth_successful"),
        pytest.param(start_reconfigure, "reconfigure_successful", id="reconfigure"),
    ],
)
async def test_update_errors(hass, start_flow, reason):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == reason
""",
            _MODULE_NAME,
            id="parametrized_successful_reason",
        ),
        pytest.param(
            """
import pytest

FLOWS = [(start_reauth, "reauth_successful")]

@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("other",), [(1,)])
@pytest.mark.parametrize("start_flow,reason", FLOWS)
async def test_update_errors(hass, other, start_flow, reason):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == reason
""",
            _MODULE_NAME,
            id="parametrized_constant",
        ),
        pytest.param(
            """
async def test_reconfigure_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    await assert_abort_flow(hass, result["flow_id"], reason="reconfigure_successful")
""",
            _MODULE_NAME,
            id="reason_keyword",
        ),
        pytest.param(
            """
def _assert_create_entry(result):
    assert result["type"] is FlowResultType.CREATE_ENTRY

async def _finish_flow(hass, result):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    _assert_create_entry(result)

async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    await _finish_flow(hass, result)
""",
            _MODULE_NAME,
            id="helper",
        ),
        pytest.param(
            """
def _assert_form(result, step_id, errors=None):
    assert result["step_id"] == step_id
    if errors is None:
        assert result.get("errors") in ({}, None)
    else:
        assert result["errors"] == errors

def _assert_abort(result, reason):
    assert result["reason"] == reason

async def test_reconfigure_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    _assert_form(result, "user")
    _assert_form(result, "user", errors={})
    _assert_form(result, "user", {"base": "cannot_connect"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    _assert_abort(result, "reconfigure_successful")
""",
            _MODULE_NAME,
            id="helper_arguments",
        ),
        pytest.param(
            """
def _assert_form(result, *, errors=None, other=None):
    assert result["errors"] == errors

def _check(result, *args):
    _assert_form(result)

async def test_form(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    _assert_form(result)
    _check(*ARGS)
""",
            _MODULE_NAME,
            id="helper_keyword_only_and_starred",
        ),
        pytest.param(
            """
async def _test_error_and_recover(hass, error):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": error}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

async def test_form_errors(hass):
    await _test_error_and_recover(hass, "cannot_connect")
""",
            _MODULE_NAME,
            id="helper_recovers_itself",
        ),
        pytest.param(
            """
async def test_form_errors(hass, scenario):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    if scenario == "error":
        assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            _MODULE_NAME,
            id="recovery_after_branch",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
""",
            "tests.components.test_integration.test_init",
            id="not_a_config_flow_test",
        ),
        pytest.param(
            """
def _check_errors(result):
    assert result["errors"] == {"base": "cannot_connect"}
""",
            _MODULE_NAME,
            id="not_a_test",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: ConfigFlowErrorRecovery,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "error_line"),
    [
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
""",
            5,
            id="error_only",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_init(DOMAIN)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            4,
            id="finished_in_new_flow",
        ),
        pytest.param(
            """
async def test_form_errors(hass, error):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": error}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
""",
            4,
            id="failure_abort",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["errors"]["base"] == "invalid_host"
""",
            8,
            id="error_after_create_entry",
        ),
        pytest.param(
            """
import pytest

@pytest.mark.parametrize("reason", ["reauth_successful", "unknown"])
async def test_update_errors(hass, reason):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == reason
""",
            7,
            id="parametrized_failure_reason",
        ),
        pytest.param(
            """
async def test_form_errors(hass, expected_errors):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("errors") == expected_errors
""",
            4,
            id="errors_argument",
        ),
        pytest.param(
            """
async def test_update_errors(hass, reason):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"].get("base") == "invalid_auth"
    assert result["reason"] == REASON
    assert result["reason"] == Reason.SUCCESS
    assert result["reason"] == reason
    unknown_helper(result)
""",
            4,
            id="unresolved_reason_and_helper",
        ),
        pytest.param(
            """
import pytest

@pytest.mark.parametrize(names, VALUES)
@pytest.mark.parametrize("reason", get_reasons())
@pytest.mark.parametrize("other_reason", UNDEFINED)
async def test_update_errors(hass, reason, other_reason):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["reason"] == reason
    assert result["reason"] == other_reason
""",
            9,
            id="unresolved_parametrize",
        ),
        pytest.param(
            """
import pytest

@pytest.mark.parametrize(("flow", "reason"), ["reauth_successful"])
async def test_update_errors(hass, flow, reason):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "invalid_auth"}
    assert result["reason"] == reason
""",
            7,
            id="parametrize_row_mismatch",
        ),
        pytest.param(
            """
def _assert_create_entry(result):
    assert result["type"] is FlowResultType.CREATE_ENTRY

def _level_2(result):
    _assert_create_entry(result)

def _level_1(result):
    _level_2(result)

async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    _level_1(result)
""",
            13,
            id="helper_too_deep",
        ),
        pytest.param(
            """
from tests.flow_helpers import assert_create_entry

async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "cannot_connect"}
    assert_create_entry(result)
""",
            6,
            id="helper_outside_integration_tests",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"]
""",
            4,
            id="truthy_errors",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert CONF_HOST in result.get("errors")
""",
            4,
            id="key_in_errors",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] != {}
""",
            4,
            id="errors_not_empty",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] is not None
""",
            4,
            id="errors_not_none",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert "errors" in result and result["errors"]["base"] == "invalid_key"
""",
            4,
            id="and_chain",
        ),
        pytest.param(
            """
def _assert_form_error(result, error):
    assert result["errors"] == {"base": error}

async def _test_form_error(hass, error):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    _assert_form_error(result, error)

async def test_form_errors(hass):
    await _test_form_error(hass, "cannot_connect")
""",
            10,
            id="helper_error",
        ),
        pytest.param(
            """
async def test_reconfigure(hass, scenario):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    if scenario == "error":
        assert result["errors"] == {"base": "invalid_auth"}
    else:
        assert result["reason"] == "reconfigure_successful"
""",
            5,
            id="recovery_in_else",
        ),
        pytest.param(
            """
async def test_reconfigure(hass, scenario):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    if scenario == "success":
        assert result["type"] is FlowResultType.CREATE_ENTRY
    elif scenario == "error":
        assert result["errors"] == {"base": "invalid_auth"}
""",
            7,
            id="recovery_in_other_elif",
        ),
        pytest.param(
            """
async def test_reconfigure(hass, scenario):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    match scenario:
        case "error":
            assert result["errors"] == {"base": "invalid_auth"}
        case _:
            assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            6,
            id="recovery_in_other_case",
        ),
        pytest.param(
            """
async def test_form_errors(hass):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    errors = result["errors"]
    assert errors.get("base") == "cannot_connect"
""",
            5,
            id="errors_alias",
        ),
        pytest.param(
            """
async def test_form_errors(hass, scenario):
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    if scenario == "auth":
        assert result["errors"] == {"base": "invalid_auth"}
    else:
        assert result["errors"] == {"base": "cannot_connect"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
""",
            5,
            id="earlier_error_unrecovered",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: ConfigFlowErrorRecovery,
    code: str,
    error_line: int,
) -> None:
    """Test cases that should trigger a warning."""
    root_node = astroid.parse(code, _MODULE_NAME)
    # The error check is the last condition of the assert on that line, or the
    # call to the helper that shows the error
    *_, error_node = (
        node
        for node in root_node.nodes_of_class(
            (nodes.Compare, nodes.Subscript, nodes.Call)
        )
        if node.lineno == error_line
        and isinstance(
            node.parent, nodes.Assert | nodes.BoolOp | nodes.Expr | nodes.Await
        )
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-tests-config-flow-error-recovery",
            node=error_node,
            line=error_node.lineno,
            col_offset=error_node.col_offset,
            end_line=error_node.end_lineno,
            end_col_offset=error_node.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)
