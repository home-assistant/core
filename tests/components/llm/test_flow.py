"""Tests for the shared LLM DataEntryFlow helpers."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant import data_entry_flow
from homeassistant.components.llm import flow as llm_flow
from homeassistant.helpers.llm import ToolResult


def test_format_result_merges_extra_placeholders() -> None:
    """Test step description_placeholders override extra_placeholders."""
    result: data_entry_flow.FlowResult[data_entry_flow.FlowContext, str] = {
        "type": data_entry_flow.FlowResultType.FORM,
        "flow_id": "flow1234",
        "handler": "test",
        "step_id": "confirm",
        "description_placeholders": {"name": "Override"},
    }
    translations = {
        "component.test.fix_flow.step.confirm.title": "{prefix}: {name}",
    }

    formatted = llm_flow.format_result(
        result,
        translations,
        "component.test.fix_flow",
        extra_placeholders={"prefix": "Fix", "name": "Original"},
    )
    assert formatted["flow_id"] == "flow1234"
    assert formatted["title"] == "Fix: Override"


async def test_configure_step_missing_and_unknown_flow() -> None:
    """Test missing flow and UnknownFlow from async_configure return errors."""
    flow_mgr = MagicMock()
    flow_mgr._progress = {}

    missing = await llm_flow.async_configure_step(flow_mgr, "flow1234")
    assert missing == ToolResult(
        data={"error": "Flow 'flow1234' not found."}, error=True
    )

    flow_handler = MagicMock()
    flow_handler.cur_step = {"type": data_entry_flow.FlowResultType.FORM}
    flow_mgr._progress = {"flow1234": flow_handler}
    flow_mgr.async_configure = AsyncMock(side_effect=data_entry_flow.UnknownFlow)

    unknown = await llm_flow.async_configure_step(
        flow_mgr,
        "flow1234",
        display_flow_id="test:1234",
        user_input={},
    )
    assert unknown == ToolResult(
        data={"error": "Flow 'test:1234' not found."}, error=True
    )
