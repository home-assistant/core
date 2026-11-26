"""Shared helpers for driving DataEntryFlow steps from LLM tools.

Integrations exposing DataEntryFlow-based workflows (such as config, options,
or repair fix flows) as LLM tools can compose these helpers to handle common
flow interaction mechanics consistently:

1. Call `async_configure_step` to validate inputs, inspect, advance, poll
   progress on, or abort an in-progress flow step. It returns either an
   error/abort `ToolResult` or the next `FlowResult`.
2. Call `format_result` to serialize the resulting `FlowResult` (`form`,
   `menu`, `progress`, `create_entry`, or `abort`) with translated titles,
   descriptions, schema fields, and errors.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant import data_entry_flow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import ToolResult, substitute_translation_placeholders
from homeassistant.util.json import JsonObjectType, JsonValueType


def _error_result(error: str) -> ToolResult:
    """Return an error ToolResult."""
    return ToolResult(data={"error": error}, error=True)


def _enrich_schema_fields(
    fields: list[dict[str, Any]],
    translations: Mapping[str, str],
    prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> list[JsonValueType]:
    """Enrich probatio.to_field_list items with resolved translations."""
    for field in fields:
        name: str = field["name"]

        if (desc_meta := field.pop("description", None)) is not None and (
            suggested_value := desc_meta.get("suggested_value")
        ) is not None:
            field["suggested_value"] = suggested_value

        if field.get("type") == "expandable":
            sec_prefix = f"{prefix}.sections.{name}"
            label_key, desc_key = f"{sec_prefix}.name", f"{sec_prefix}.description"
            _enrich_schema_fields(
                field["schema"], translations, sec_prefix, placeholders
            )
        else:
            label_key, desc_key = (
                f"{prefix}.data.{name}",
                f"{prefix}.data_description.{name}",
            )

        if label := substitute_translation_placeholders(
            translations.get(label_key), placeholders
        ):
            field["label"] = label
        if description := substitute_translation_placeholders(
            translations.get(desc_key), placeholders
        ):
            field["description"] = description

    return fields  # type: ignore[return-value]


def format_result(
    result: data_entry_flow.FlowResult[Any, Any],
    translations: Mapping[str, str],
    base_prefix: str,
    *,
    flow_id: str | None = None,
    fallback_title: str | None = None,
    extra_placeholders: Mapping[str, Any] | None = None,
    fallback_abort_description: str | None = None,
) -> JsonObjectType:
    """Format a DataEntryFlow result with resolved translations for LLM consumption.

    `base_prefix` is the flattened translation key prefix for the flow
    (for example, ``component.<domain>.config`` or
    ``component.<domain>.issues.<key>.fix_flow``). Callers handle flow-specific
    concerns such as `EXTERNAL_STEP` rejection or attaching extra result fields
    (like `entry_id`) to the returned dictionary.

    `flow_id` defaults to ``result["flow_id"]`` when omitted. `extra_placeholders`,
    when provided, are merged beneath the step's own `description_placeholders`.
    `fallback_title` and `fallback_abort_description` are used when the
    corresponding keys are absent from `translations`.
    """
    flow_type = result["type"]
    step_placeholders: Mapping[str, Any] | None = result.get("description_placeholders")
    if extra_placeholders and step_placeholders:
        placeholders: Mapping[str, Any] | None = {
            **extra_placeholders,
            **step_placeholders,
        }
    else:
        placeholders = step_placeholders or extra_placeholders

    formatted: JsonObjectType = {
        "flow_id": flow_id or result["flow_id"],
        "type": str(flow_type),
    }

    if (step_id := result.get("step_id")) is not None:
        formatted["step_id"] = step_id
        step_prefix = f"{base_prefix}.step.{step_id}"
        if title := substitute_translation_placeholders(
            translations.get(f"{step_prefix}.title") or fallback_title,
            placeholders,
        ):
            formatted["title"] = title
        if description := substitute_translation_placeholders(
            translations.get(f"{step_prefix}.description"), placeholders
        ):
            formatted["description"] = description

        if flow_type is data_entry_flow.FlowResultType.FORM:
            if (last_step := result.get("last_step")) is not None:
                formatted["last_step"] = last_step
            raw_fields: list[dict[str, Any]] = []
            if (schema := result.get("data_schema")) is not None:
                raw_fields = probatio.to_field_list(  # type: ignore[assignment]
                    schema, custom_serializer=cv.custom_serializer
                )
                data_entry_flow.add_visible_conditions_to_serialized_schema(
                    schema, raw_fields
                )
            formatted["fields"] = _enrich_schema_fields(
                raw_fields, translations, step_prefix, placeholders
            )
            if err_source := result.get("errors"):
                formatted["errors"] = {
                    err_field: (
                        substitute_translation_placeholders(
                            translations.get(f"{base_prefix}.error.{err_val}", err_val),
                            placeholders,
                        )
                        or err_val
                    )
                    for err_field, err_val in err_source.items()
                }
        elif flow_type is data_entry_flow.FlowResultType.MENU:
            raw_opts: Any = result.get("menu_options", [])
            formatted["menu_options"] = {
                opt: (
                    substitute_translation_placeholders(
                        translations.get(f"{step_prefix}.menu_options.{opt}")
                        or (raw_opts[opt] if isinstance(raw_opts, dict) else opt),
                        placeholders,
                    )
                    or opt
                )
                for opt in raw_opts
            }
        elif flow_type is data_entry_flow.FlowResultType.SHOW_PROGRESS:
            progress_action = result["progress_action"]
            formatted["progress_action"] = progress_action
            if description := substitute_translation_placeholders(
                translations.get(f"{base_prefix}.progress.{progress_action}"),
                placeholders,
            ):
                formatted["description"] = description

    elif flow_type is data_entry_flow.FlowResultType.CREATE_ENTRY:
        if title := result.get("title"):
            formatted["title"] = title
        desc_key = result.get("description") or "default"
        if desc := substitute_translation_placeholders(
            translations.get(f"{base_prefix}.create_entry.{desc_key}"), placeholders
        ):
            formatted["description"] = desc

    elif flow_type is data_entry_flow.FlowResultType.ABORT:
        reason = result["reason"]
        formatted["reason"] = reason
        abort_msg = (
            translations.get(f"{base_prefix}.abort.{reason}")
            or fallback_abort_description
        )
        if abort_text := substitute_translation_placeholders(abort_msg, placeholders):
            formatted["description"] = abort_text

    return formatted


async def async_configure_step[
    _FlowContextT: data_entry_flow.FlowContext,
    _FlowResultT: data_entry_flow.FlowResult[Any, Any],
    _HandlerT,
](
    flow_mgr: data_entry_flow.FlowManager[_FlowContextT, _FlowResultT, _HandlerT],
    flow_id: str,
    *,
    display_flow_id: str | None = None,
    user_input: dict[str, Any] | None = None,
    next_step_id: str | None = None,
    abort: bool = False,
) -> _FlowResultT | ToolResult:
    """Validate inputs and inspect, advance, poll, or abort an in-progress flow step.

    Returns a `ToolResult` directly when input arguments are invalid, when the
    flow is not found, when `abort` is true, when input does not match the
    current step type, or when `async_configure` raises `InvalidData` or
    `UnknownFlow`. Otherwise returns the current `FlowResult` when inspecting
    a form/menu or waiting for a progress task, or the next `FlowResult` when
    advancing the flow, for the caller to format with `format_result`.
    """
    if user_input is not None and next_step_id is not None:
        return _error_result("Cannot specify both 'user_input' and 'next_step_id'.")
    if user_input is not None and "next_step_id" in user_input:
        return _error_result(
            "Use the 'next_step_id' parameter instead of 'user_input' "
            "to select a menu option."
        )

    shown_id = display_flow_id or flow_id
    if (flow_handler := flow_mgr._progress.get(flow_id)) is None:  # noqa: SLF001
        return _error_result(f"Flow '{shown_id}' not found.")

    cur_step = flow_handler.cur_step
    if TYPE_CHECKING:
        assert cur_step is not None

    if abort:
        flow_mgr.async_abort(flow_id)
        return ToolResult(
            data={
                "result": {
                    "flow_id": shown_id,
                    "type": "abort",
                    "reason": "aborted",
                }
            }
        )

    cur_type = cur_step.get("type")
    if cur_type is data_entry_flow.FlowResultType.MENU and user_input is not None:
        return _error_result(
            "Current step is a 'menu' step; pass the chosen option in "
            "'next_step_id' instead of 'user_input'."
        )
    if cur_type is data_entry_flow.FlowResultType.FORM and next_step_id is not None:
        return _error_result(
            "Current step is a 'form' step; pass field values in "
            "'user_input' instead of 'next_step_id'."
        )
    if cur_type not in (
        data_entry_flow.FlowResultType.FORM,
        data_entry_flow.FlowResultType.MENU,
    ) and (user_input is not None or next_step_id is not None):
        return _error_result(
            f"Current step has type '{cur_type}' and does not accept input."
        )

    if (
        cur_type
        in (data_entry_flow.FlowResultType.FORM, data_entry_flow.FlowResultType.MENU)
        and user_input is None
        and next_step_id is None
    ):
        return cur_step

    if (
        cur_type is data_entry_flow.FlowResultType.SHOW_PROGRESS
        and (progress_task := flow_handler.async_get_progress_task()) is not None
        and not progress_task.done()
    ):
        return cur_step

    flow_input: dict[str, Any] | None = (
        {"next_step_id": next_step_id} if next_step_id is not None else user_input
    )
    try:
        return await flow_mgr.async_configure(flow_id, flow_input)
    except data_entry_flow.InvalidData as err:
        return _error_result(f"Invalid input: {err.schema_errors}")
    except data_entry_flow.UnknownFlow:
        return _error_result(f"Flow '{shown_id}' not found.")
