"""LLM tools for the config integration."""

from collections import defaultdict
from collections.abc import Iterable, Iterator
import heapq
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


def _resolve_language(hass: HomeAssistant, language: str | None) -> str:
    """Resolve a translation language code from an LLMContext language."""
    return language if language and language != "*" else (hass.config.language or "en")


def _format_short_entry_ids(entries: Iterable[ConfigEntry]) -> dict[str, str]:
    """Return a mapping of full entry_id to short '<domain>:<suffix>' ID.

    Short IDs reduce token usage and LLM transcription errors across tool calls.
    The trailing suffix starts at 4 characters and expands if another entry in the
    same domain shares that suffix.
    """
    groups: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in entries:
        groups[(entry.domain, entry.entry_id[-_MIN_SHORT_ID_LEN:])].append(
            entry.entry_id
        )

    result: dict[str, str] = {}
    for (domain, _), group in groups.items():
        length = _MIN_SHORT_ID_LEN
        while len(group) > 1 and len({eid[-length:] for eid in group}) < len(group):
            length += 1
        for eid in group:
            result[eid] = f"{domain}:{eid[-length:]}"
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


def _rank_integration(
    query: str,
    domain: str,
    name: str,
    brand_name: str | None,
    other: Iterable[str],
) -> int | None:
    """Return the match rank for a case-folded query, or None if it does not match.

    Lower numbers rank higher when sorting with heapq.nsmallest:
    - 0: exact match on name or domain
    - 1: exact match on brand name
    - 2: substring match on name or domain
    - 3: substring match on brand name, supported_by, or iot_standards
    """
    domain_folded = domain.casefold()
    name_folded = name.casefold()
    if query in (name_folded, domain_folded):
        return 0
    brand_folded = brand_name.casefold() if brand_name else ""
    if brand_folded == query:
        return 1
    if query in name_folded or query in domain_folded:
        return 2
    if (brand_folded and query in brand_folded) or any(
        query in item.casefold() for item in other
    ):
        return 3
    return None


def _match_searchable_entry(
    query: str,
    domain: str,
    meta: dict[str, Any],
    title_trans: dict[str, str],
    brand_name: str | None = None,
) -> tuple[int, str, str, JsonObjectType] | None:
    """Rank an integration description and build its result dict if matched."""
    if meta.get("integration_type") == "hardware":
        return None
    supported_by: str | None = meta.get("supported_by")
    iot_standards: list[str] | None = meta.get("iot_standards")
    has_config_flow = bool(meta.get("config_flow", False))
    if not (has_config_flow or supported_by or iot_standards):
        return None

    name: str = (
        meta.get("name") or title_trans.get(f"component.{domain}.title") or domain
    )
    other = (*((supported_by,) if supported_by else ()), *(iot_standards or ()))
    if (rank := _rank_integration(query, domain, name, brand_name, other)) is None:
        return None

    entry_info: JsonObjectType = {
        "domain": domain,
        "name": name,
        "config_flow": has_config_flow,
    }
    if supported_by:
        entry_info["supported_by"] = supported_by
    if iot_standards:
        entry_info["iot_standards"] = list[JsonValueType](iot_standards)
    if meta.get("single_config_entry"):
        entry_info["single_config_entry"] = True
    return (rank, name.casefold(), domain, entry_info)


def _iter_searchable_matches(
    query: str,
    descriptions: dict[str, Any],
    title_trans: dict[str, str],
    filter_type: str | None,
) -> Iterator[tuple[int, str, str, JsonObjectType]]:
    """Yield ranked integration matches for query."""
    if filter_type in (None, "integration"):
        integrations = (
            descriptions["core"]["integration"] | descriptions["custom"]["integration"]
        )
        for key, info in integrations.items():
            if "integration_type" in info or not info.get("integrations"):
                if match := _match_searchable_entry(query, key, info, title_trans):
                    yield match
                continue
            brand_name = info.get("name", key)
            for sub_domain, sub_info in info["integrations"].items():
                if match := _match_searchable_entry(
                    query, sub_domain, sub_info, title_trans, brand_name=brand_name
                ):
                    yield match

    if filter_type in (None, "helper"):
        helpers = descriptions["core"]["helper"] | descriptions["custom"]["helper"]
        for domain, info in helpers.items():
            if match := _match_searchable_entry(query, domain, info, title_trans):
                yield match


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

        short_ids = _format_short_entry_ids(entries)

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
        "Search the catalog of all available Home Assistant integrations and helpers "
        "(including uninstalled ones) by name, domain, brand, or IoT standard "
        "(use config__get_config_entries instead to list integrations that are already "
        "installed). Returns whether the integration supports a UI config_flow, or if "
        "it is a virtual integration supported_by another integration domain or IoT "
        "standard (zigbee, zwave, matter, homekit)."
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
                    "Search text to match against integration name, domain, brand, "
                    "or IoT standard (case-insensitive)."
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
                    entry_info for _, _, _, entry_info in best
                )
            }
        )


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
        ]
    )
