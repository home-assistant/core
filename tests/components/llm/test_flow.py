"""Tests for the shared LLM DataEntryFlow helpers."""

from unittest.mock import AsyncMock, MagicMock

import probatio
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.llm import flow as llm_flow
from homeassistant.helpers.llm import ToolResult


def test_format_result_form_sections_and_errors() -> None:
    """Test FORM formatting with sections, suggested values, placeholders, and errors."""
    schema = probatio.Schema(
        {
            probatio.Required("host", description={"suggested_value": "10.0.0.1"}): str,
            probatio.Optional("advanced"): data_entry_flow.section(
                probatio.Schema({probatio.Optional("port", default=80): int})
            ),
        }
    )
    result: data_entry_flow.FlowResult[data_entry_flow.FlowContext, str] = {
        "type": data_entry_flow.FlowResultType.FORM,
        "flow_id": "flow1234",
        "handler": "test",
        "step_id": "config",
        "data_schema": schema,
        "errors": {"host": "cannot_connect"},
        "last_step": False,
        "description_placeholders": {"name": "Override"},
    }
    translations = {
        "component.test.flow.step.config.description": "Configure {name}",
        "component.test.flow.step.config.data.host": "Host",
        "component.test.flow.step.config.data_description.host": "IP for {prefix}",
        "component.test.flow.step.config.sections.advanced.name": "Advanced",
        "component.test.flow.step.config.sections.advanced.description": "Extra",
        "component.test.flow.step.config.sections.advanced.data.port": "Port",
        "component.test.flow.error.cannot_connect": "Failed for {name}",
    }

    formatted = llm_flow.format_result(
        result,
        translations,
        "component.test.flow",
        fallback_title="{prefix}: {name}",
        extra_placeholders={"prefix": "Fix", "name": "Original"},
    )
    assert formatted["flow_id"] == "flow1234"
    assert formatted["type"] == "form"
    assert formatted["step_id"] == "config"
    assert formatted["title"] == "Fix: Override"
    assert formatted["description"] == "Configure Override"
    assert formatted["last_step"] is False
    assert formatted["errors"] == {"host": "Failed for Override"}
    fields = formatted["fields"]
    assert isinstance(fields, list)
    assert fields[0]["suggested_value"] == "10.0.0.1"
    assert fields[0]["label"] == "Host"
    assert fields[0]["description"] == "IP for Fix"
    assert fields[1]["label"] == "Advanced"
    assert fields[1]["description"] == "Extra"
    assert fields[1]["schema"][0]["label"] == "Port"


@pytest.mark.parametrize(
    ("result", "translations", "kwargs", "expected"),
    [
        pytest.param(
            {
                "type": data_entry_flow.FlowResultType.MENU,
                "flow_id": "flow1234",
                "handler": "test",
                "step_id": "pick",
                "menu_options": {"a": "Label A", "b": "Label B"},
            },
            {"component.test.flow.step.pick.menu_options.a": "Translated A"},
            {"flow_id": "test:1234"},
            {
                "flow_id": "test:1234",
                "type": "menu",
                "step_id": "pick",
                "menu_options": {"a": "Translated A", "b": "Label B"},
            },
            id="menu_dict_options",
        ),
        pytest.param(
            {
                "type": data_entry_flow.FlowResultType.SHOW_PROGRESS,
                "flow_id": "flow1234",
                "handler": "test",
                "step_id": "wait",
                "progress_action": "pairing",
            },
            {"component.test.flow.progress.pairing": "Waiting..."},
            {},
            {
                "flow_id": "flow1234",
                "type": "progress",
                "step_id": "wait",
                "progress_action": "pairing",
                "description": "Waiting...",
            },
            id="show_progress",
        ),
        pytest.param(
            {
                "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
                "flow_id": "flow1234",
                "handler": "test",
                "title": "Done",
            },
            {"component.test.flow.create_entry.default": "Created entry."},
            {},
            {
                "flow_id": "flow1234",
                "type": "create_entry",
                "title": "Done",
                "description": "Created entry.",
            },
            id="create_entry",
        ),
        pytest.param(
            {
                "type": data_entry_flow.FlowResultType.ABORT,
                "flow_id": "flow1234",
                "handler": "test",
                "reason": "already_configured",
            },
            {},
            {"fallback_abort_description": "Fallback abort."},
            {
                "flow_id": "flow1234",
                "type": "abort",
                "reason": "already_configured",
                "description": "Fallback abort.",
            },
            id="abort_fallback",
        ),
    ],
)
def test_format_result_variants(
    result: data_entry_flow.FlowResult[data_entry_flow.FlowContext, str],
    translations: dict[str, str],
    kwargs: dict[str, str],
    expected: dict[str, object],
) -> None:
    """Test MENU, SHOW_PROGRESS, CREATE_ENTRY, and ABORT result formatting."""
    assert (
        llm_flow.format_result(result, translations, "component.test.flow", **kwargs)
        == expected
    )


@pytest.mark.parametrize(
    ("cur_type", "kwargs", "expected_error"),
    [
        pytest.param(
            data_entry_flow.FlowResultType.FORM,
            {"user_input": {}, "next_step_id": "a"},
            "Cannot specify both 'user_input' and 'next_step_id'.",
            id="both_inputs",
        ),
        pytest.param(
            data_entry_flow.FlowResultType.FORM,
            {"user_input": {"next_step_id": "a"}},
            "Use the 'next_step_id' parameter instead of 'user_input' to select a menu option.",
            id="nested_next_step_id",
        ),
        pytest.param(
            data_entry_flow.FlowResultType.MENU,
            {"user_input": {}},
            "Current step is a 'menu' step; pass the chosen option in 'next_step_id' instead of 'user_input'.",
            id="user_input_on_menu",
        ),
        pytest.param(
            data_entry_flow.FlowResultType.FORM,
            {"next_step_id": "a"},
            "Current step is a 'form' step; pass field values in 'user_input' instead of 'next_step_id'.",
            id="next_step_id_on_form",
        ),
        pytest.param(
            data_entry_flow.FlowResultType.SHOW_PROGRESS,
            {"user_input": {}},
            "Current step has type 'progress' and does not accept input.",
            id="input_on_progress",
        ),
    ],
)
async def test_configure_step_input_validation(
    cur_type: data_entry_flow.FlowResultType,
    kwargs: dict[str, object],
    expected_error: str,
) -> None:
    """Test step input mismatches return error ToolResults without calling configure."""
    flow_handler = MagicMock(cur_step={"type": cur_type})
    flow_mgr = MagicMock(_progress={"flow1234": flow_handler})
    flow_mgr.async_configure = AsyncMock()

    result = await llm_flow.async_configure_step(flow_mgr, "flow1234", **kwargs)
    assert result == ToolResult(data={"error": expected_error}, error=True)
    flow_mgr.async_configure.assert_not_awaited()


async def test_configure_step_abort_and_progress() -> None:
    """Test abort, in-progress polling, and advancing after progress completes."""
    task = MagicMock()
    task.done.return_value = False
    progress_step = {
        "type": data_entry_flow.FlowResultType.SHOW_PROGRESS,
        "flow_id": "flow1234",
        "step_id": "wait",
        "progress_action": "working",
    }
    flow_handler = MagicMock(cur_step=progress_step)
    flow_handler.async_get_progress_task.return_value = task
    flow_mgr = MagicMock(_progress={"flow1234": flow_handler})
    next_step = {
        "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
        "flow_id": "flow1234",
    }
    flow_mgr.async_configure = AsyncMock(return_value=next_step)

    # While progress task is running, returns current step without calling configure
    assert await llm_flow.async_configure_step(flow_mgr, "flow1234") is progress_step
    flow_mgr.async_configure.assert_not_awaited()

    # Once progress task finishes, calls async_configure(flow_id, None)
    task.done.return_value = True
    assert await llm_flow.async_configure_step(flow_mgr, "flow1234") is next_step
    flow_mgr.async_configure.assert_awaited_once_with("flow1234", None)

    # Explicit abort
    aborted = await llm_flow.async_configure_step(
        flow_mgr, "flow1234", display_flow_id="test:1234", abort=True
    )
    flow_mgr.async_abort.assert_called_once_with("flow1234")
    assert aborted == ToolResult(
        data={
            "result": {
                "flow_id": "test:1234",
                "type": "abort",
                "reason": "aborted",
            }
        }
    )


async def test_configure_step_errors_and_menu_forwarding() -> None:
    """Test missing flow, InvalidData, UnknownFlow, and menu option forwarding."""
    flow_mgr = MagicMock(_progress={})
    assert await llm_flow.async_configure_step(flow_mgr, "flow1234") == ToolResult(
        data={"error": "Flow 'flow1234' not found."}, error=True
    )

    flow_handler = MagicMock(cur_step={"type": data_entry_flow.FlowResultType.MENU})
    flow_mgr._progress = {"flow1234": flow_handler}
    flow_mgr.async_configure = AsyncMock(
        side_effect=[
            {
                "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
                "flow_id": "flow1234",
            },
            data_entry_flow.InvalidData(
                "Invalid", ["host"], "required", {"host": "required"}
            ),
            data_entry_flow.UnknownFlow,
        ]
    )

    await llm_flow.async_configure_step(flow_mgr, "flow1234", next_step_id="opt_a")
    flow_mgr.async_configure.assert_awaited_with("flow1234", {"next_step_id": "opt_a"})

    invalid = await llm_flow.async_configure_step(
        flow_mgr, "flow1234", next_step_id="opt_a"
    )
    assert invalid == ToolResult(
        data={"error": "Invalid input: {'host': 'required'}"}, error=True
    )

    unknown = await llm_flow.async_configure_step(
        flow_mgr, "flow1234", display_flow_id="test:1234", next_step_id="opt_a"
    )
    assert unknown == ToolResult(
        data={"error": "Flow 'test:1234' not found."}, error=True
    )
