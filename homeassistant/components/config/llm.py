"""LLM tools for the config integration."""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
import heapq
import re
from typing import Any, override

import probatio

from homeassistant import config_entries
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import translation
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.loader import async_get_integration_descriptions
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN

_SEARCH_LIMIT = 15
_INTEGRATION_FILTER_TYPES = ["integration", "helper"]
_STATUS_VALUES = ["loaded", "error", "not_loaded"]
_STATUS_STATES: dict[str, set[ConfigEntryState]] = {
    "loaded": {ConfigEntryState.LOADED},
    "error": {
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
        ConfigEntryState.FAILED_UNLOAD,
    },
    "not_loaded": {
        ConfigEntryState.NOT_LOADED,
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.UNLOAD_IN_PROGRESS,
    },
}
_NON_EMPTY_STRING = probatio.All(str, probatio.Strip, probatio.NonEmpty())
_MIN_SHORT_ID_LEN = 4
_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


def _resolve_language(hass: HomeAssistant, language: str | None) -> str:
    """Resolve a translation language code from an LLMContext language."""
    return language if language and language != "*" else (hass.config.language or "en")


def _interpolate_placeholders(
    text: str | None, placeholders: Mapping[str, Any] | None
) -> str | None:
    """Replace {key} placeholders in text using a single regex pass."""
    if not text or not placeholders:
        return text
    return _PLACEHOLDER_RE.sub(
        lambda m: (
            str(val)
            if (val := placeholders.get(m.group(1))) is not None
            else m.group(0)
        ),
        text,
    )


def _format_short_ids(items: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Return a mapping of full ID to short '<domain>:<suffix>' ID.

    Short IDs reduce token usage and LLM transcription errors across tool calls.
    The trailing suffix starts at 4 characters and expands if another item in the
    same domain shares that suffix.
    """
    groups: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for domain, item_id in items:
        groups[(domain, item_id[-_MIN_SHORT_ID_LEN:])].append(item_id)

    result: dict[str, str] = {}
    for (domain, _), group in groups.items():
        length = _MIN_SHORT_ID_LEN
        while len(group) > 1 and len({iid[-length:] for iid in group}) < len(group):
            length += 1
        for iid in group:
            result[iid] = f"{domain}:{iid[-length:]}"
    return result


def _resolve_short_entry_id(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    """Resolve a ConfigEntry from a '<domain>:<suffix>' short ID."""
    domain, sep, suffix = entry_id.partition(":")
    if not sep or not domain or len(suffix) < _MIN_SHORT_ID_LEN:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")

    matches = [
        candidate
        for candidate in hass.config_entries.async_entries(domain.lower())
        if candidate.entry_id.endswith(suffix)
    ]
    if len(matches) != 1:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")

    return matches[0]


def _resolve_entry_reason(entry: ConfigEntry) -> str | None:
    """Resolve a human-readable error reason for a ConfigEntry."""
    if key := entry.error_reason_translation_key:
        message = translation.async_get_exception_message(
            entry.error_reason_translation_domain or entry.domain,
            key,
            entry.error_reason_translation_placeholders,
        )
        if message != key:
            return message
        return entry.reason or key
    return entry.reason


def _error_result(error: str) -> ToolResult:
    """Return an error ToolResult."""
    return ToolResult(data={"error": error}, error=True)


def _format_config_entry(entry: ConfigEntry, short_id: str) -> JsonObjectType:
    """Format a ConfigEntry into a compact dictionary for LLM consumption."""
    result: JsonObjectType = {
        "entry_id": short_id,
        "domain": entry.domain,
        "title": entry.title,
        "state": entry.state.value,
    }
    if entry.disabled_by is not None:
        result["disabled_by"] = entry.disabled_by.value
    if entry.source == config_entries.SOURCE_IGNORE:
        result["source"] = entry.source
    if (reason := _resolve_entry_reason(entry)) is not None:
        result["reason"] = reason
    return result


def _iter_searchable_matches(
    query: str,
    descriptions: dict[str, Any],
    title_trans: dict[str, str],
    filter_type: str | None,
) -> Iterator[tuple[int, str, str, str]]:
    """Yield (rank, sort_name, domain, name) for config-flow integrations matching query.

    Lower rank numbers sort first with heapq.nsmallest:
    - 0: exact match on domain or name
    - 1: exact match on brand name
    - 2: substring match on domain or name
    - 3: substring match on brand name
    """
    sources: list[tuple[str, dict[str, Any], str]] = []
    if filter_type in (None, "integration"):
        for key, info in (
            descriptions["core"]["integration"] | descriptions["custom"]["integration"]
        ).items():
            if "integration_type" in info:
                sources.append((key, info, ""))
            elif sub := info.get("integrations"):
                brand = info.get("name", key).casefold()
                sources.extend((dom, meta, brand) for dom, meta in sub.items())
    if filter_type in (None, "helper"):
        sources.extend(
            (dom, meta, "")
            for dom, meta in (
                descriptions["core"]["helper"] | descriptions["custom"]["helper"]
            ).items()
        )

    for domain, meta, brand in sources:
        # Exclude YAML-only, hardware, virtual, and IoT-standard-only entries for now.
        if not meta.get("config_flow"):
            continue
        name = (
            meta.get("name") or title_trans.get(f"component.{domain}.title") or domain
        )
        dom_f, name_f = domain.casefold(), name.casefold()
        if query in (dom_f, name_f):
            rank = 0
        elif query == brand:
            rank = 1
        elif query in dom_f or query in name_f:
            rank = 2
        elif brand and query in brand:
            rank = 3
        else:
            continue
        yield (rank, name_f, domain, name)


class GetConfigEntriesTool(Tool):
    """LLM Tool to list and filter config entries."""

    name = "config__get_config_entries"
    title = "Get config entries"
    description = (
        "Retrieve installed Home Assistant config entries (configured integrations "
        "and helpers). Use this to inspect which integrations are set up, check their "
        "status ('loaded', 'error', 'not_loaded'), and see translated error reasons."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "domain",
                description=(
                    "Filter by integration domain (e.g. 'hue', 'zwave_js'). "
                    "Accepts a single domain or a list of domains."
                ),
            ): probatio.Any(
                _NON_EMPTY_STRING,
                probatio.All([_NON_EMPTY_STRING], probatio.Length(min=1)),
            ),
            probatio.Optional(
                "status",
                description=(
                    "Filter by status: 'loaded' (working normally), 'error' "
                    "(failed setup, retrying, migration error, or failed unload), "
                    "or 'not_loaded' (including disabled or ignored entries)."
                ),
            ): probatio.All(str, probatio.Lower, probatio.In(_STATUS_VALUES)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return matching config entries."""
        args = self.parameters(tool_input.tool_args)
        domain_filter: str | list[str] | None = args.get("domain")
        status_filter: str | None = args.get("status")

        entries = hass.config_entries.async_entries(
            include_ignore=True, include_disabled=True
        )

        if domain_filter is not None:
            domains = {
                d.lower()
                for d in (
                    (domain_filter,)
                    if isinstance(domain_filter, str)
                    else domain_filter
                )
            }
            entries = [entry for entry in entries if entry.domain.lower() in domains]

        short_ids = _format_short_ids(
            (entry.domain, entry.entry_id) for entry in entries
        )

        if status_filter is not None:
            allowed_states = _STATUS_STATES[status_filter]
            entries = [entry for entry in entries if entry.state in allowed_states]

        return ToolResult(
            data={
                "result": list[JsonValueType](
                    _format_config_entry(entry, short_ids[entry.entry_id])
                    for entry in entries
                )
            }
        )


class ReloadConfigEntryTool(Tool):
    """LLM Tool to reload a config entry."""

    name = "config__reload_config_entry"
    title = "Reload config entry"
    description = (
        "Reload an installed Home Assistant config entry by entry_id. Use this to "
        "recover an integration from a transient setup or connection error or apply "
        "changes."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "entry_id",
                description=(
                    "The entry_id of the config entry to reload (e.g. 'hue:8K2M')."
                ),
            ): _NON_EMPTY_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Reload the specified config entry."""
        args = self.parameters(tool_input.tool_args)
        entry_id: str = args["entry_id"]

        try:
            entry = _resolve_short_entry_id(hass, entry_id)
        except HomeAssistantError as err:
            return _error_result(str(err))

        if entry.disabled_by is not None:
            return _error_result(
                f"Config entry '{entry_id}' cannot be reloaded because it is disabled."
            )
        if entry.source == config_entries.SOURCE_IGNORE:
            return _error_result(
                f"Config entry '{entry_id}' cannot be reloaded because it is ignored."
            )

        try:
            await hass.config_entries.async_reload(entry.entry_id)
        except config_entries.OperationNotAllowed:
            return _error_result(
                f"Config entry '{entry_id}' cannot be reloaded in state "
                f"'{entry.state.value}'."
            )

        result: JsonObjectType = {
            "entry_id": entry_id,
            "state": entry.state.value,
        }
        if (reason := _resolve_entry_reason(entry)) is not None:
            result["reason"] = reason

        return ToolResult(data={"result": result})


class SearchIntegrationsTool(Tool):
    """LLM Tool to search available integrations and helpers."""

    name = "config__search_integrations"
    title = "Search available integrations"
    description = (
        "Search the catalog of available Home Assistant integrations and helpers "
        "that can be set up via a config flow (including uninstalled ones) by name, "
        "domain, or brand. Use config__get_config_entries instead to list "
        "integrations that are already installed."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "query",
                description=(
                    "Search text to match against integration name, domain, or "
                    "brand (case-insensitive)."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "type",
                description="Filter results by type: 'integration' or 'helper'.",
            ): probatio.All(
                str, probatio.Lower, probatio.In(_INTEGRATION_FILTER_TYPES)
            ),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Search available integrations and helpers."""
        args = self.parameters(tool_input.tool_args)
        query = args["query"].casefold()
        filter_type: str | None = args.get("type")

        descriptions = await async_get_integration_descriptions(hass)
        lang = _resolve_language(hass, llm_context.language)
        title_trans = await translation.async_get_translations(
            hass,
            lang,
            "title",
            set(descriptions["core"].get("translated_name", ())),
        )

        best = heapq.nsmallest(
            _SEARCH_LIMIT,
            _iter_searchable_matches(query, descriptions, title_trans, filter_type),
        )
        return ToolResult(
            data={
                "result": list[JsonValueType](
                    {"domain": domain, "name": name} for _, _, domain, name in best
                )
            }
        )


class GetFlowsInProgressTool(Tool):
    """LLM Tool to list pending discovery and reauth config flows."""

    name = "config__get_flows_in_progress"
    title = "Get config flows in progress"
    description = (
        "List non-user-initiated config flows currently in progress, such as "
        "newly discovered devices on the network (zeroconf, bluetooth, ssdp, dhcp, "
        "mqtt, usb) and integrations requiring reauthentication (reauth)."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "domain",
                description="Filter in-progress flows by integration domain.",
            ): _NON_EMPTY_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """List non-user-initiated flows in progress."""
        args = self.parameters(tool_input.tool_args)
        domain_filter: str | None = args.get("domain")

        all_flows = hass.config_entries.flow.async_progress()
        flows = [
            flw
            for flw in all_flows
            if flw["context"]["source"]
            not in (config_entries.SOURCE_RECONFIGURE, config_entries.SOURCE_USER)
            and (domain_filter is None or flw["handler"] == domain_filter)
        ]

        if not flows:
            return ToolResult(data={"result": []})

        lang = _resolve_language(hass, llm_context.language)
        handlers = {flw["handler"] for flw in flows}
        config_trans = await translation.async_get_translations(
            hass, lang, "config", handlers
        )
        title_trans = await translation.async_get_translations(
            hass, lang, "title", handlers
        )
        short_flow_ids = _format_short_ids(
            (flw["handler"], flw["flow_id"]) for flw in all_flows
        )
        short_entry_ids = (
            _format_short_ids(
                (entry.domain, entry.entry_id)
                for entry in hass.config_entries.async_entries(
                    include_ignore=True, include_disabled=True
                )
            )
            if any("entry_id" in flw["context"] for flw in flows)
            else {}
        )

        results: list[JsonValueType] = []
        for flw in flows:
            handler = flw["handler"]
            context = flw["context"]
            flow_title: str | None = None
            if placeholders := context.get("title_placeholders"):
                if (
                    template := config_trans.get(
                        f"component.{handler}.config.flow_title"
                    )
                ) and all(
                    placeholders.get(m.group(1)) is not None
                    for m in _PLACEHOLDER_RE.finditer(template)
                ):
                    flow_title = _interpolate_placeholders(template, placeholders)
                else:
                    flow_title = placeholders.get("name")
            if not flow_title:
                flow_title = title_trans.get(f"component.{handler}.title", handler)

            item: JsonObjectType = {
                "flow_id": short_flow_ids[flw["flow_id"]],
                "domain": handler,
                "source": context["source"],
                "title": flow_title,
            }
            if (step_id := flw.get("step_id")) is not None:
                item["step_id"] = step_id
            if (entry_id := context.get("entry_id")) is not None and (
                short_id := short_entry_ids.get(entry_id)
            ) is not None:
                item["entry_id"] = short_id
            results.append(item)

        return ToolResult(data={"result": results})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the config LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(
        tools=[
            GetConfigEntriesTool(),
            ReloadConfigEntryTool(),
            SearchIntegrationsTool(),
            GetFlowsInProgressTool(),
        ]
    )
