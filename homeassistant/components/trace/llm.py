"""LLM tools for the trace integration."""

from collections.abc import Iterator
from datetime import datetime
import json
from typing import Any, override

import probatio

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    SHORT_ID_MIN_LENGTH,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
    format_short_ids,
)
from homeassistant.util.json import JsonObjectType

from . import DOMAIN
from .const import DATA_TRACE, TRACE_DOMAINS
from .models import BaseTrace
from .util import async_restore_traces


def _domain_traces(hass: HomeAssistant, domain: str) -> Iterator[BaseTrace]:
    """Yield the stored traces of all automations or all scripts."""
    for key, trace_bucket in hass.data[DATA_TRACE].items():
        if key.startswith(f"{domain}."):
            yield from trace_bucket.all_traces()


def _short_trace_ids(hass: HomeAssistant, domain: str) -> dict[str, str]:
    """Return a mapping of run_id to short '<domain>:<suffix>' trace ID."""
    return format_short_ids(
        (domain, trace.run_id) for trace in _domain_traces(hass, domain)
    )


def _parse_int(value: str) -> int | str:
    """Return an integer, or its text when it does not fit in 64 bits."""
    number = int(value)
    return number if -(2**63) <= number < 2**64 else value


def _isoformat(value: Any) -> Any:
    """Return a datetime as ISO string; restored traces already hold strings."""
    return value.isoformat() if isinstance(value, datetime) else value


def _format_summary(trace: BaseTrace, trace_id: str) -> JsonObjectType:
    """Format the summary of a trace for LLM consumption."""
    short = trace.as_short_dict()
    result: JsonObjectType = {
        "trace_id": trace_id,
        "start": _isoformat(short["timestamp"]["start"]),
        "finish": _isoformat(short["timestamp"]["finish"]),
        "state": short["state"],
        "script_execution": short["script_execution"],
        "last_step": short["last_step"],
    }
    for key in ("trigger", "error", "not_triggered"):
        if short.get(key):
            result[key] = short[key]
    return result


class ListTracesTool(Tool):
    """LLM Tool to list the stored runs of an automation or script."""

    name = "trace__list_traces"
    title = "List traces"
    description = (
        "List the stored runs of an automation or script, newest first, with when "
        "they started and finished, how they ended, what triggered them and their "
        "error. Home Assistant keeps the last runs of each automation and script, "
        "5 by default. A run with not_triggered was a trigger that did not fire. "
        "Use the trace_id with trace__get_trace to see each step of a run."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "entity_id",
                description="The entity_id of the automation or script.",
            ): cv.entity_domain(list(TRACE_DOMAINS)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the stored runs of the automation or script."""
        entity_id: str = self.parameters(tool_input.tool_args)["entity_id"]
        domain = split_entity_id(entity_id)[0]
        # Traces are stored under the unique ID, which an automation only has
        # when its configuration has an id.
        entry = er.async_get(hass).async_get(entity_id)
        if entry is None or entry.platform != domain:
            raise HomeAssistantError(
                f"'{entity_id}' not found, or it has no id to store traces under."
            )

        await async_restore_traces(hass)
        trace_bucket = hass.data[DATA_TRACE].get(f"{domain}.{entry.unique_id}")
        traces = sorted(
            trace_bucket.all_traces() if trace_bucket else [],
            key=lambda trace: _isoformat(trace.as_short_dict()["timestamp"]["start"]),
            reverse=True,
        )
        short_ids = _short_trace_ids(hass, domain)
        return ToolResult(
            data={
                "traces": [
                    _format_summary(trace, short_ids[trace.run_id]) for trace in traces
                ]
            }
        )


class GetTraceTool(Tool):
    """LLM Tool to get one run of an automation or script."""

    name = "trace__get_trace"
    title = "Get trace"
    description = (
        "Get one run of an automation or script: each step in the order it ran, "
        "with its path in the configuration, result, error and changed variables. "
        "Use trace__list_traces to find the trace_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "trace_id", description="The trace_id, like 'automation:3f2a'."
            ): probatio.All(str, probatio.Strip, probatio.NonEmpty()),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the steps of the run."""
        trace_id: str = self.parameters(tool_input.tool_args)["trace_id"]
        domain, sep, suffix = trace_id.partition(":")
        if not sep or domain not in TRACE_DOMAINS or len(suffix) < SHORT_ID_MIN_LENGTH:
            raise HomeAssistantError(f"Trace '{trace_id}' not found.")

        await async_restore_traces(hass)
        matches = [
            trace
            for trace in _domain_traces(hass, domain)
            if trace.run_id.endswith(suffix)
        ]
        if len(matches) != 1:
            raise HomeAssistantError(f"Trace '{trace_id}' not found.")
        trace = matches[0]

        extended = trace.as_extended_dict()
        child_short_ids: dict[str, dict[str, str]] = {}
        steps: list[dict[str, Any]] = []
        for elements in extended["trace"].values():
            for element in elements:
                step = dict(element)
                if child := step.pop("child_id", None):
                    child_domain = child["domain"]
                    if child_domain not in child_short_ids:
                        child_short_ids[child_domain] = _short_trace_ids(
                            hass, child_domain
                        )
                    if child_trace_id := child_short_ids[child_domain].get(
                        child["run_id"]
                    ):
                        step["child_trace_id"] = child_trace_id
                steps.append(step)
        steps.sort(key=lambda step: _isoformat(step["timestamp"]))

        result: dict[str, Any] = {
            **_format_summary(trace, _short_trace_ids(hass, domain)[trace.run_id]),
            "entity_id": er.async_get(hass).async_get_entity_id(
                domain, domain, extended["item_id"]
            ),
            "steps": steps,
        }
        # Trace steps hold any variable. Each value that JSON cannot hold falls
        # back to its repr, NaN and infinity become null, and integers too big
        # for the JSON encoders of Home Assistant become text.
        data: JsonObjectType = json.loads(
            json.dumps(result, cls=ExtendedJSONEncoder),
            parse_constant=lambda _: None,
            parse_int=_parse_int,
        )
        return ToolResult(data=data)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the trace LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[ListTracesTool(), GetTraceTool()])
