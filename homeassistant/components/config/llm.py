"""LLM tools for the config integration."""

from collections.abc import Iterable, Iterator
from contextlib import suppress
import heapq
from typing import Any, Literal, override

import probatio

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.llm import LLMTools, flow as llm_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlowResult,
    ConfigSubentry,
    SubentryFlowResult,
)
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import DependencyError, HomeAssistantError
from homeassistant.generated.integration_categories import INTEGRATION_CATEGORIES
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
    translation,
)
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
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.loader import (
    IntegrationNotFound,
    async_get_integration,
    async_get_integration_descriptions,
)
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN
from .core import UPDATE_CONFIG_SCHEMA, async_update_config

_SEARCH_LIMIT = 15
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
_DOMAIN_STRING = probatio.All(str, probatio.Strip, probatio.Lower, probatio.NonEmpty())
_OAUTH_RUNTIME_ERRORS = ("No current request in context", "No header in request")
type _FlowCategory = Literal["config", "options", "config_subentries"]
_FLOW_TYPES = ["config", "options", "reconfigure", "subentry"]
_UPDATE_CORE_CONFIG_SCHEMA = probatio.Schema(UPDATE_CONFIG_SCHEMA)


def _resolve_language(hass: HomeAssistant, language: str | None) -> str:
    """Resolve a translation language code from an LLMContext language."""
    return language if language and language != "*" else (hass.config.language or "en")


def _format_short_entry_ids(entries: Iterable[ConfigEntry]) -> dict[str, str]:
    """Return a mapping of full entry_id to short '<domain>:<suffix>' ID."""
    return format_short_ids((entry.domain, entry.entry_id) for entry in entries)


def _resolve_short_entry_id(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    """Resolve a ConfigEntry from a '<domain>:<suffix>' short ID."""
    domain, sep, suffix = entry_id.partition(":")
    if not sep or not domain or len(suffix) < SHORT_ID_MIN_LENGTH:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")

    matches = [
        candidate
        for candidate in hass.config_entries.async_entries(domain)
        if candidate.entry_id.endswith(suffix)
    ]
    if len(matches) != 1:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")

    return matches[0]


def _resolve_short_subentry_id(entry: ConfigEntry, subentry_id: str) -> ConfigSubentry:
    """Resolve a ConfigSubentry from a '<subentry_type>:<suffix>' short ID."""
    subentry_type, sep, suffix = subentry_id.rpartition(":")
    if not sep or not subentry_type or len(suffix) < SHORT_ID_MIN_LENGTH:
        raise HomeAssistantError(f"Subentry '{subentry_id}' not found.")

    matches = [
        candidate
        for candidate in entry.get_subentries_of_type(subentry_type)
        if candidate.subentry_id.endswith(suffix)
    ]
    if len(matches) != 1:
        raise HomeAssistantError(f"Subentry '{subentry_id}' not found.")

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
    if entry.state is ConfigEntryState.LOADED and entry.supports_options:
        result["supports_options"] = True
    if (
        entry.disabled_by is None
        and entry.source != config_entries.SOURCE_IGNORE
        and entry.supports_reconfigure
    ):
        result["supports_reconfigure"] = True
    if (
        entry.disabled_by is None
        and entry.source != config_entries.SOURCE_IGNORE
        and entry.supported_subentry_types
    ):
        result["supported_subentry_types"] = {
            sub_type: dict[str, JsonValueType](sub_meta)
            for sub_type, sub_meta in entry.supported_subentry_types.items()
        }
    if entry.subentries:
        short_subentry_ids = format_short_ids(
            (subentry.subentry_type, subentry.subentry_id)
            for subentry in entry.subentries.values()
        )
        result["subentries"] = [
            {
                "subentry_id": short_subentry_ids[subentry.subentry_id],
                "subentry_type": subentry.subentry_type,
                "title": subentry.title,
            }
            for subentry in entry.subentries.values()
        ]
    return result


def _iter_searchable_matches(
    query: str,
    descriptions: dict[str, Any],
    title_trans: dict[str, str],
    category: str | None,
) -> Iterator[tuple[int, str, str, str, list[str]]]:
    """Yield (rank, sort_name, domain, name, categories) for matching config-flow integrations.

    Lower rank numbers sort first with heapq.nsmallest:
    - 0: exact match on domain or name
    - 1: all query words match domain or name
    - 2: all query words match domain, name, or brand
    """
    sources: list[tuple[str, dict[str, Any], str]] = []
    for key, info in (
        descriptions["core"]["integration"] | descriptions["custom"]["integration"]
    ).items():
        if "integration_type" in info:
            sources.append((key, info, ""))
        elif sub := info.get("integrations"):
            brand = info.get("name", key).casefold()
            sources.extend((dom, meta, brand) for dom, meta in sub.items())
    sources.extend(
        (dom, meta, "")
        for dom, meta in (
            descriptions["core"]["helper"] | descriptions["custom"]["helper"]
        ).items()
    )

    words = query.replace("_", " ").split()
    seen: set[str] = set()
    for domain, meta, brand in sources:
        # Exclude YAML-only, hardware, virtual, and IoT-standard-only entries for now.
        if domain in seen or not meta.get("config_flow"):
            continue
        name = (
            meta.get("name") or title_trans.get(f"component.{domain}.title") or domain
        )
        name_f = name.casefold()
        head = f"{domain} {name_f}".replace("_", " ")
        if not all(word in f"{head} {brand}" for word in words):
            continue
        categories: list[str] = meta.get("categories", [])
        # Categories can be subcategories, like 'energy.energy_prices'
        if category is not None and not any(
            cat.partition(".")[0] == category for cat in categories
        ):
            continue
        seen.add(domain)
        if query in (domain, name_f):
            rank = 0
        elif all(word in head for word in words):
            rank = 1
        else:
            rank = 2
        yield (rank, name_f, domain, name, categories)


class GetConfigEntriesTool(Tool):
    """LLM Tool to list and filter config entries."""

    name = "config__get_config_entries"
    title = "Get config entries"
    description = (
        "Retrieve installed Home Assistant config entries (configured integrations "
        "and helpers). Use this to inspect which integrations are set up, check their "
        "status ('loaded', 'error', 'not_loaded'), see translated error reasons, and "
        "find entry_ids, subentries, and supported flow capabilities "
        "(supports_options, supports_reconfigure, supported_subentry_types)."
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
            ): probatio.All(
                probatio.EnsureList(),
                [_DOMAIN_STRING],
                probatio.Length(min=1),
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
        domain_filter: list[str] | None = args.get("domain")
        status_filter: str | None = args.get("status")

        entries = hass.config_entries.async_entries(
            include_ignore=True, include_disabled=True
        )
        if domain_filter is not None:
            entries = [entry for entry in entries if entry.domain in domain_filter]

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
        "Search the catalog of available Home Assistant integrations and helpers "
        "that can be set up via a config flow (including uninstalled ones) by name, "
        "domain, brand, or category. Returns at most "
        f"{_SEARCH_LIMIT} results per call. Use config__get_config_entries instead "
        "to list integrations that are already installed."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "query",
                description=(
                    "Search text to match against integration name, domain, or "
                    "brand (case-insensitive). Required if 'category' is not given."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "category",
                description=(
                    "Filter results by category. Use 'helpers' to find helpers, "
                    "and 'local_services' for waste collection, power outages "
                    "and other city or utility information."
                ),
            ): probatio.In(INTEGRATION_CATEGORIES),
            probatio.Optional(
                "offset",
                description=(
                    "Number of results to skip. Use the next_offset of the "
                    "previous result."
                ),
                default=0,
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=0)),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Search available integrations and helpers."""
        args = self.parameters(tool_input.tool_args)
        if "query" not in args and "category" not in args:
            raise probatio.Invalid("Either 'query' or 'category' is required.")
        query = args.get("query", "").casefold()
        category: str | None = args.get("category")
        offset: int = args["offset"]

        lang = _resolve_language(hass, llm_context.language)
        descriptions = await async_get_integration_descriptions(hass)
        title_trans = await translation.async_get_translations(
            hass,
            lang,
            "title",
            set(descriptions["core"].get("translated_name", ())),
        )

        matches = list(
            _iter_searchable_matches(query, descriptions, title_trans, category)
        )
        best = heapq.nsmallest(offset + _SEARCH_LIMIT, matches)[offset:]
        result: JsonObjectType = {
            "result": list[JsonValueType](
                {
                    "domain": domain,
                    "name": name,
                    "categories": list[JsonValueType](categories),
                }
                for _, _, domain, name, categories in best
            ),
            "total": len(matches),
        }
        if (next_offset := offset + _SEARCH_LIMIT) < len(matches):
            result["next_offset"] = next_offset
        return ToolResult(data=result)


def _resolve_short_flow_id(
    hass: HomeAssistant, flow_id: str
) -> tuple[
    data_entry_flow.FlowManager[Any, Any, Any], ConfigFlowResult | SubentryFlowResult
]:
    """Resolve an active flow from a '<domain>:<suffix>' short ID."""
    domain, sep, suffix = flow_id.partition(":")
    if not sep or not domain or len(suffix) < SHORT_ID_MIN_LENGTH:
        raise HomeAssistantError(f"Flow '{flow_id}' not found.")

    flow_mgr = hass.config_entries.flow
    matches: list[
        tuple[
            data_entry_flow.FlowManager[Any, Any, Any],
            ConfigFlowResult | SubentryFlowResult,
        ]
    ] = [
        (flow_mgr, flw)
        for flw in flow_mgr.async_progress_by_handler(domain)
        if flw["flow_id"].endswith(suffix)
    ]

    options_mgr = hass.config_entries.options
    subentry_mgr = hass.config_entries.subentries
    entry_ids = {entry.entry_id for entry in hass.config_entries.async_entries(domain)}
    for entry_id in entry_ids:
        matches.extend(
            (options_mgr, flw)
            for flw in options_mgr.async_progress_by_handler(entry_id)
            if flw["flow_id"].endswith(suffix)
        )
    matches.extend(
        (subentry_mgr, flw)
        for flw in subentry_mgr.async_progress()
        if flw["handler"][0] in entry_ids and flw["flow_id"].endswith(suffix)
    )
    if not matches:
        # Allow aborting subentry flows whose parent entry was removed.
        matches.extend(
            (subentry_mgr, flw)
            for flw in subentry_mgr.async_progress()
            if flw["flow_id"].endswith(suffix)
            and hass.config_entries.async_get_entry(flw["handler"][0]) is None
        )

    if len(matches) != 1:
        raise HomeAssistantError(f"Flow '{flow_id}' not found.")

    return matches[0]


def _build_external_step_error(domain: str, *, is_new_entry: bool = True) -> ToolResult:
    """Return an error ToolResult directing the user to complete OAuth/external setup in the UI."""
    frontend_url = (
        f"/config/integrations/dashboard/add?domain={domain}"
        if is_new_entry
        else f"/config/integrations/integration/{domain}"
    )
    return ToolResult(
        data={
            "error": (
                f"Integration '{domain}' requires browser authentication (OAuth / external step) "
                f"and must be configured in the Home Assistant UI at {frontend_url}."
            ),
            "frontend_url": frontend_url,
        },
        error=True,
    )


async def _async_finalize_flow_step(
    hass: HomeAssistant,
    flow_mgr: data_entry_flow.FlowManager[Any, Any, Any],
    result: ConfigFlowResult | SubentryFlowResult,
    domain: str,
    language: str | None,
    *,
    flow_category: _FlowCategory = "config",
    subentry_type: str | None = None,
    is_new_entry: bool = True,
) -> ToolResult:
    """Handle external/OAuth steps or format a DataEntryFlow result with translations."""
    flow_type = result["type"]
    if (
        flow_type is data_entry_flow.FlowResultType.EXTERNAL_STEP
        or result.get("step_id") == "pick_implementation"
    ):
        with suppress(data_entry_flow.UnknownFlow):
            flow_mgr.async_abort(result["flow_id"])
        return _build_external_step_error(domain, is_new_entry=is_new_entry)
    if (
        flow_type is data_entry_flow.FlowResultType.ABORT
        and result.get("reason") == "missing_credentials"
    ):
        return _build_external_step_error(domain, is_new_entry=is_new_entry)

    lang = _resolve_language(hass, language)
    trans_domain: str = result.get("translation_domain") or domain
    trans_domains = {domain, trans_domain}
    if flow_category == "config":
        trans_domains.add("homeassistant")
    trans = await translation.async_get_translations(
        hass, lang, flow_category, trans_domains
    )
    title_trans = await translation.async_get_translations(
        hass, lang, "title", {domain}
    )
    if flow_category == "config_subentries":
        base_prefix = f"component.{trans_domain}.config_subentries.{subentry_type}"
    else:
        base_prefix = f"component.{trans_domain}.{flow_category}"

    fallback_abort: str | None = None
    if flow_type is data_entry_flow.FlowResultType.ABORT:
        reason = result["reason"]
        if not trans.get(f"{base_prefix}.abort.{reason}"):
            abort_trans = (
                trans
                if flow_category == "config"
                else await translation.async_get_translations(
                    hass, lang, "config", {"homeassistant"}
                )
            )
            fallback_abort = abort_trans.get(
                f"component.homeassistant.config.abort.{reason}"
            )

    flow_id = f"{domain}:{result['flow_id'][-SHORT_ID_MIN_LENGTH:]}"
    formatted = llm_flow.format_result(
        result,
        trans,
        base_prefix,
        flow_id=flow_id,
        fallback_title=title_trans.get(f"component.{domain}.title"),
        fallback_abort_description=fallback_abort,
    )
    if flow_type is data_entry_flow.FlowResultType.CREATE_ENTRY and isinstance(
        created_entry := result.get("result"), ConfigEntry
    ):
        formatted["entry_id"] = _format_short_entry_ids(
            hass.config_entries.async_entries(created_entry.domain)
        )[created_entry.entry_id]

    return ToolResult(data={"result": formatted})


class GetFlowsInProgressTool(Tool):
    """LLM Tool to list pending discovery and reauth config flows."""

    name = "config__get_flows_in_progress"
    title = "Get config flows in progress"
    description = (
        "List non-user-initiated config flows currently in progress, such as "
        "newly discovered devices on the network (zeroconf, bluetooth, ssdp, dhcp, "
        "mqtt, usb) and integrations requiring reauthentication (reauth). Use the "
        "returned flow_id with config__configure_flow to inspect or complete a flow."
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
            ): _DOMAIN_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """List non-user-initiated flows in progress."""
        args = self.parameters(tool_input.tool_args)
        domain_filter: str | None = args.get("domain")

        flows = []
        for flw in hass.config_entries.flow.async_progress():
            if flw["context"]["source"] in (
                config_entries.SOURCE_RECONFIGURE,
                config_entries.SOURCE_USER,
            ):
                continue
            if domain_filter is not None and flw["handler"] != domain_filter:
                continue
            flows.append(flw)
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
        short_entry_ids = _format_short_entry_ids(
            hass.config_entries.async_entries(
                include_ignore=True, include_disabled=True
            )
        )

        results: list[JsonValueType] = []
        for flw in flows:
            handler = flw["handler"]
            context = flw["context"]
            flow_title: str | None = None
            if placeholders := context.get("title_placeholders"):
                if template := config_trans.get(
                    f"component.{handler}.config.flow_title"
                ):
                    with suppress(KeyError):
                        flow_title = template.format_map(placeholders)
                if not flow_title:
                    flow_title = placeholders.get("name")
            if not flow_title:
                flow_title = title_trans.get(f"component.{handler}.title", handler)

            item: JsonObjectType = {
                "flow_id": f"{handler}:{flw['flow_id'][-SHORT_ID_MIN_LENGTH:]}",
                "domain": handler,
                "source": context["source"],
                "title": flow_title,
            }
            if (step_id := flw.get("step_id")) is not None:
                item["step_id"] = step_id
            if short_id := short_entry_ids.get(context.get("entry_id", "")):
                item["entry_id"] = short_id
            results.append(item)

        return ToolResult(data={"result": results})


def _resolve_subentry_start_params(
    entry: ConfigEntry,
    entry_id: str,
    flow_type: str,
    subentry_type: str | None,
    subentry_id: str | None,
) -> tuple[str, config_entries.SubentryFlowContext, str]:
    """Validate and build (subentry_type, context, unsupported_msg) for a subentry flow."""
    if flow_type == "reconfigure" and subentry_id is None:
        raise HomeAssistantError(
            "'subentry_id' is required when reconfiguring a subentry."
        )
    if subentry_id is not None:
        subentry = _resolve_short_subentry_id(entry, subentry_id)
        if subentry_type is not None and subentry.subentry_type != subentry_type:
            raise HomeAssistantError(
                f"Subentry '{subentry_id}' does not match subentry_type "
                f"'{subentry_type}'."
            )
        return (
            subentry.subentry_type,
            {
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": subentry.subentry_id,
            },
            f"Subentry '{subentry_id}' does not support reconfigure.",
        )
    if subentry_type is None:
        raise HomeAssistantError(
            "'subentry_type' is required when starting a subentry flow."
        )
    return (
        subentry_type,
        {"source": config_entries.SOURCE_USER},
        f"Config entry '{entry_id}' does not support subentry type '{subentry_type}'.",
    )


class StartFlowTool(Tool):
    """LLM Tool to start a configuration, options, reconfigure, or subentry flow."""

    name = "config__start_flow"
    title = "Start configuration flow"
    description = (
        "Start a configuration, options, reconfigure, or subentry flow in Home "
        "Assistant and return its initial step.\n"
        "- 'config' (default): set up a new integration or helper instance by 'domain'.\n"
        "- 'options': update runtime options on a loaded config entry by 'entry_id' "
        "(requires supports_options).\n"
        "- 'reconfigure': update connection or authentication settings on an existing "
        "config entry by 'entry_id' (requires supports_reconfigure), or on an existing "
        "subentry by also passing 'subentry_id'.\n"
        "- 'subentry': add a child subentry on an existing config entry by 'entry_id' "
        "and 'subentry_type' (from supported_subentry_types), or reconfigure an "
        "existing subentry by passing 'subentry_id'."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=True
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "flow_type",
                description=(
                    "Type of flow to start: 'config' (new entry, default), "
                    "'options', 'reconfigure', or 'subentry'."
                ),
                default="config",
            ): probatio.All(str, probatio.Lower, probatio.In(_FLOW_TYPES)),
            probatio.Optional(
                "domain",
                description=(
                    "Integration domain to set up when flow_type is 'config' "
                    "(e.g. 'local_todo', 'template')."
                ),
            ): _DOMAIN_STRING,
            probatio.Optional(
                "entry_id",
                description=(
                    "The entry_id of the config entry when flow_type is 'options', "
                    "'reconfigure', or 'subentry' (e.g. 'hue:8K2M')."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "subentry_type",
                description=(
                    "Subentry type key from supported_subentry_types when adding a "
                    "new subentry with flow_type 'subentry' (optional when "
                    "'subentry_id' is given)."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "subentry_id",
                description=(
                    "The subentry_id of an existing subentry to reconfigure "
                    "(e.g. 'conversation:8K2M')."
                ),
            ): _NON_EMPTY_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Start the requested flow and return its formatted initial step."""
        args = self.parameters(tool_input.tool_args)
        flow_type: str = args["flow_type"]
        domain: str | None = args.get("domain")
        entry_id: str | None = args.get("entry_id")
        subentry_type: str | None = args.get("subentry_type")
        subentry_id: str | None = args.get("subentry_id")

        if domain is not None and entry_id is not None:
            return _error_result("Cannot specify both 'domain' and 'entry_id'.")
        if (subentry_type is not None or subentry_id is not None) and flow_type not in (
            "subentry",
            "reconfigure",
        ):
            return _error_result(
                "'subentry_type' and 'subentry_id' are only valid when flow_type "
                "is 'subentry' or 'reconfigure'."
            )

        flow_mgr: data_entry_flow.FlowManager[Any, Any, Any]
        handler: Any
        context: Any
        flow_category: _FlowCategory = "config"
        if flow_type == "config":
            if entry_id is not None:
                return _error_result(
                    "Specify 'flow_type' ('options', 'reconfigure', or 'subentry') "
                    "when passing 'entry_id'."
                )
            if domain is None:
                return _error_result("'domain' is required when flow_type is 'config'.")
            flow_mgr = hass.config_entries.flow
            handler = domain
            target_domain = domain
            context = {"source": config_entries.SOURCE_USER}
            unsupported_msg = f"Integration '{domain}' does not exist or does not support config flows."
        else:
            if entry_id is None:
                return _error_result(
                    f"'entry_id' is required when flow_type is '{flow_type}'."
                )
            try:
                entry = _resolve_short_entry_id(hass, entry_id)
            except HomeAssistantError as err:
                return _error_result(str(err))
            if entry.disabled_by is not None:
                return _error_result(
                    f"Config entry '{entry_id}' cannot be configured because it is disabled."
                )
            if entry.source == config_entries.SOURCE_IGNORE:
                return _error_result(
                    f"Config entry '{entry_id}' cannot be configured because it is ignored."
                )
            target_domain = entry.domain
            if flow_type == "options":
                unsupported_msg = f"Config entry '{entry_id}' does not support options."
                if entry.state is not ConfigEntryState.LOADED:
                    return _error_result(
                        f"Config entry '{entry_id}' must be loaded to configure "
                        f"options (current state: '{entry.state.value}')."
                    )
                if entry.domain not in config_entries.HANDLERS:
                    with suppress(IntegrationNotFound, ImportError):
                        integration = await async_get_integration(hass, entry.domain)
                        await integration.async_get_platform("config_flow")
                if not entry.supports_options:
                    return _error_result(unsupported_msg)
                flow_mgr = hass.config_entries.options
                handler = entry.entry_id
                flow_category = "options"
                context = {}
            elif (
                flow_type == "reconfigure"
                and subentry_type is None
                and subentry_id is None
            ):
                unsupported_msg = (
                    f"Config entry '{entry_id}' does not support reconfigure."
                )
                flow_mgr = hass.config_entries.flow
                handler = entry.domain
                context = {
                    "source": config_entries.SOURCE_RECONFIGURE,
                    "entry_id": entry.entry_id,
                }
            else:
                try:
                    subentry_type, context, unsupported_msg = (
                        _resolve_subentry_start_params(
                            entry, entry_id, flow_type, subentry_type, subentry_id
                        )
                    )
                except HomeAssistantError as err:
                    return _error_result(str(err))
                flow_mgr = hass.config_entries.subentries
                handler = (entry.entry_id, subentry_type)
                flow_category = "config_subentries"

        is_new_entry = flow_type == "config"
        try:
            result = await flow_mgr.async_init(handler, context=context)
        except data_entry_flow.UnknownHandler, data_entry_flow.UnknownStep:
            return _error_result(unsupported_msg)
        except DependencyError as err:
            return _error_result(
                f"Failed dependencies: {', '.join(err.failed_dependencies)}"
            )
        except RuntimeError as err:
            if str(err) not in _OAUTH_RUNTIME_ERRORS:
                raise
            for flw in flow_mgr.async_progress_by_handler(
                handler, include_uninitialized=True
            ):
                if flw["context"] is context:
                    flow_mgr.async_abort(flw["flow_id"])
            return _build_external_step_error(target_domain, is_new_entry=is_new_entry)

        return await _async_finalize_flow_step(
            hass,
            flow_mgr,
            result,
            target_domain,
            llm_context.language,
            flow_category=flow_category,
            subentry_type=subentry_type,
            is_new_entry=is_new_entry,
        )


class ConfigureFlowTool(Tool):
    """LLM Tool to inspect, advance, or abort an in-progress flow."""

    name = "config__configure_flow"
    title = "Configure flow step"
    description = (
        "Inspect, submit input to, or abort an in-progress configuration, options, "
        "reconfigure, or subentry flow by flow_id.\n"
        "- To inspect the current step without submitting, omit both 'user_input' and 'next_step_id'.\n"
        "- To submit a 'form' step, pass field values in 'user_input' (pass {} for "
        "a confirmation form with no fields).\n"
        "- To select an option in a 'menu' step, pass the option key in 'next_step_id'.\n"
        "- To cancel/abort the flow, set 'abort' to true."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=True
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "flow_id",
                description="The flow_id of the in-progress flow (e.g. 'random:8K2M').",
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "user_input",
                description=(
                    "Field values to submit when the current step has type 'form' "
                    "(pass {} to confirm an empty form). Omit to fetch the current step state."
                ),
            ): dict,
            probatio.Optional(
                "next_step_id",
                description=(
                    "Menu option key to select when the current step has type 'menu'."
                ),
            ): _NON_EMPTY_STRING,
            probatio.Optional(
                "abort",
                description="Set to true to cancel and abort the flow (default: false).",
                default=False,
            ): probatio.All(probatio.Boolean(), bool),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Configure or abort the specified flow."""
        args = self.parameters(tool_input.tool_args)
        short_flow_id: str = args["flow_id"]
        user_input: dict[str, Any] | None = args.get("user_input")
        next_step_id: str | None = args.get("next_step_id")
        abort: bool = args["abort"]

        try:
            flow_mgr, flw = _resolve_short_flow_id(hass, short_flow_id)
        except HomeAssistantError as err:
            return _error_result(str(err))

        flow_id = flw["flow_id"]
        handler = flw["handler"]
        subentry_type: str | None = None
        if isinstance(handler, tuple):
            entry_id, subentry_type = handler
            if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
                if not abort:
                    flow_mgr.async_abort(flow_id)
                    return _error_result("Config entry or subentry no longer exists.")
                domain = ""
            else:
                domain = entry.domain
            flow_category: _FlowCategory = "config_subentries"
            is_new_entry = False
        elif flow_mgr is hass.config_entries.options:
            domain = hass.config_entries.async_get_known_entry(handler).domain
            flow_category = "options"
            is_new_entry = False
        else:
            domain = handler
            flow_category = "config"
            is_new_entry = flw["context"].get("source") not in (
                config_entries.SOURCE_REAUTH,
                config_entries.SOURCE_RECONFIGURE,
            )

        try:
            step_result = await llm_flow.async_configure_step(
                flow_mgr,
                flow_id,
                display_flow_id=short_flow_id,
                user_input=user_input,
                next_step_id=next_step_id,
                abort=abort,
            )
        except config_entries.UnknownEntry, config_entries.UnknownSubEntry:
            with suppress(data_entry_flow.UnknownFlow):
                flow_mgr.async_abort(flow_id)
            return _error_result("Config entry or subentry no longer exists.")
        except RuntimeError as err:
            if str(err) not in _OAUTH_RUNTIME_ERRORS:
                raise
            flow_mgr.async_abort(flow_id)
            return _build_external_step_error(domain, is_new_entry=is_new_entry)

        if isinstance(step_result, ToolResult):
            return step_result

        return await _async_finalize_flow_step(
            hass,
            flow_mgr,
            step_result,
            domain,
            llm_context.language,
            flow_category=flow_category,
            subentry_type=subentry_type,
            is_new_entry=is_new_entry,
        )


def _url_in_use(hass: HomeAssistant, *, internal: bool) -> str | None:
    """Return the internal or external URL that Home Assistant uses."""
    try:
        return get_url(hass, allow_internal=internal, allow_external=not internal)
    except NoURLAvailableError:
        return None


def _format_core_config(hass: HomeAssistant) -> JsonObjectType:
    """Return the core config fields that the update tool manages."""
    config = hass.config
    return {
        "location_name": config.location_name,
        "latitude": config.latitude,
        "longitude": config.longitude,
        "elevation": config.elevation,
        "radius": config.radius,
        "time_zone": config.time_zone,
        "country": config.country,
        "currency": config.currency,
        "language": config.language,
        # Integrations must not use the name of the unit system, so it is private
        "unit_system": config.units._name,  # noqa: SLF001
        "internal_url": config.internal_url,
        "internal_url_in_use": _url_in_use(hass, internal=True),
        "external_url": config.external_url,
        "external_url_in_use": _url_in_use(hass, internal=False),
    }


class GetCoreConfigTool(Tool):
    """LLM Tool to get the core config."""

    name = "config__get_core_config"
    title = "Get core config"
    description = (
        "Get the core config of Home Assistant: the name and location of the home, "
        "the radius of the home zone in meters, the time zone, country, currency, "
        "language, unit system, and the internal and external URLs. internal_url "
        "and external_url are only set to override the URLs that Home Assistant "
        "finds itself: the local network address, and the Home Assistant Cloud "
        "address. The *_in_use fields show the URLs that Home Assistant uses."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the core config."""
        return ToolResult(data={"result": _format_core_config(hass)})


class UpdateCoreConfigTool(Tool):
    """LLM Tool to update the core config."""

    name = "config__update_core_config"
    title = "Update core config"
    description = (
        "Update the core config of Home Assistant. Only the given fields change."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Optional(
                "location_name", description="The name of the home."
            ): str,
            probatio.Optional("latitude"): probatio.Coerce(float),
            probatio.Optional("longitude"): probatio.Coerce(float),
            probatio.Optional(
                "elevation", description="Elevation in meters above sea level."
            ): probatio.Coerce(int),
            probatio.Optional(
                "radius", description="Radius of the home zone in meters."
            ): probatio.Coerce(int),
            probatio.Optional(
                "time_zone", description="IANA time zone, e.g. 'Europe/Amsterdam'."
            ): str,
            probatio.Optional(
                "country", description="ISO 3166-1 alpha-2 country code, e.g. 'NL'."
            ): str,
            probatio.Optional(
                "currency", description="ISO 4217 currency code, e.g. 'EUR'."
            ): str,
            probatio.Optional(
                "language", description="Language code, e.g. 'en' or 'pt-BR'."
            ): str,
            probatio.Optional(
                "unit_system",
                description=(
                    "A new unit system also changes the units of sensors, except "
                    "units the user set."
                ),
            ): probatio.In(["metric", "us_customary"]),
            probatio.Optional(
                "internal_url",
                description=(
                    "URL of Home Assistant on the local network. Only set it when "
                    "the URL in use does not work. null lets Home Assistant find it."
                ),
            ): probatio.Any(str, None),
            probatio.Optional(
                "external_url",
                description=(
                    "URL of Home Assistant on the internet. Only set it when the "
                    "URL in use does not work. null lets Home Assistant find it."
                ),
            ): probatio.Any(str, None),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the core config."""
        args = self.parameters(tool_input.tool_args)
        # Like the UI, a new unit system also changes the units of the sensors
        current_unit_system = hass.config.units._name  # noqa: SLF001
        if args.get("unit_system", current_unit_system) != current_unit_system:
            args["update_units"] = True
        try:
            data = _UPDATE_CORE_CONFIG_SCHEMA(args)
        except probatio.Invalid as err:
            return _error_result(f"Invalid input: {err}")
        try:
            await async_update_config(hass, data)
        except ValueError as err:
            return _error_result(str(err))
        return ToolResult(data={"result": _format_core_config(hass)})


def _get_entity_entry(hass: HomeAssistant, entity_id: str) -> er.RegistryEntry:
    """Return the registry entry of an entity."""
    if (entry := er.async_get(hass).async_get(entity_id)) is None:
        raise HomeAssistantError(
            f"Entity '{entity_id}' not found. Entities without a unique ID have "
            "no settings."
        )
    return entry


def _format_entity_settings(
    hass: HomeAssistant, entry: er.RegistryEntry
) -> JsonObjectType:
    """Format the settings of an entity for LLM consumption."""
    return {
        "entity_id": entry.entity_id,
        "full_name": er.async_get_full_entity_name(hass, entry),
        "name": entry.name,
        "original_name": entry.original_name,
        "icon": entry.icon,
        "area_id": entry.area_id,
        "device_id": entry.device_id,
        "device_class": entry.device_class,
        "original_device_class": entry.original_device_class,
        "disabled_by": entry.disabled_by,
        "hidden_by": entry.hidden_by,
        "aliases": [None if a is er.COMPUTED_NAME else a for a in entry.aliases],
        "labels": list[JsonValueType](sorted(entry.labels)),
        "platform": entry.platform,
    }


_NULLABLE_STRING = probatio.Any(None, _NON_EMPTY_STRING)


class GetEntitySettingsTool(Tool):
    """LLM Tool to get the settings of an entity."""

    name = "config__get_entity_settings"
    title = "Get entity settings"
    description = (
        "Get the settings of the entity with the given entity_id. Use "
        "search__search to find the entity_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("entity_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the settings of the entity."""
        args = self.parameters(tool_input.tool_args)
        entry = _get_entity_entry(hass, args["entity_id"])
        return ToolResult(data={"result": _format_entity_settings(hass, entry)})


class UpdateEntitySettingsTool(Tool):
    """LLM Tool to update the settings of an entity."""

    name = "config__update_entity_settings"
    title = "Update entity settings"
    description = (
        "Update the settings of the entity with the given entity_id. Only the "
        "given settings change. Returns the new settings."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required("entity_id"): _NON_EMPTY_STRING,
            probatio.Optional(
                "name",
                description=(
                    "The name of the entity. null uses the name from the "
                    "integration. An empty string names the entity after its "
                    "device only."
                ),
            ): probatio.Any(None, probatio.All(str, probatio.Strip)),
            probatio.Optional(
                "icon",
                description=(
                    "The icon, like 'mdi:lamp'. null uses the icon from the "
                    "integration."
                ),
            ): probatio.Any(None, probatio.All(str, cv.icon)),
            probatio.Optional(
                "area_id",
                description="The area_id. null uses the area of the device.",
            ): _NULLABLE_STRING,
            probatio.Optional(
                "device_class",
                description=(
                    "The device class, like 'outlet' for a switch. null uses the "
                    "device class from the integration."
                ),
            ): _NULLABLE_STRING,
            probatio.Optional(
                "new_entity_id",
                description=(
                    "A new entity_id. Automations and scripts that use the old one "
                    "are not updated."
                ),
            ): probatio.All(str, cv.entity_id),
            probatio.Optional(
                "disabled_by",
                description=(
                    "'user' disables the entity, null enables it. A disabled "
                    "entity has no state."
                ),
            ): probatio.Any(None, er.RegistryEntryDisabler.USER.value),
            probatio.Optional(
                "hidden_by",
                description=(
                    "'user' hides the entity from auto-populated dashboards, null "
                    "shows it."
                ),
            ): probatio.Any(None, er.RegistryEntryHider.USER.value),
            probatio.Optional(
                "aliases",
                description=(
                    "The names that voice assistants know the entity by. This "
                    "replaces all aliases. null stands for the name of the entity."
                ),
            ): [_NULLABLE_STRING],
            probatio.Optional(
                "labels",
                description="The label_ids. This replaces all labels.",
            ): [_NON_EMPTY_STRING],
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the settings of the entity and return the new settings."""
        settings = self.parameters(tool_input.tool_args)
        entity_id = settings.pop("entity_id")
        entry = _get_entity_entry(hass, entity_id)
        if (area_id := settings.get("area_id")) and ar.async_get(hass).async_get_area(
            area_id
        ) is None:
            raise HomeAssistantError(f"Area '{area_id}' not found.")
        if "labels" in settings:
            settings["labels"] = set(settings["labels"])
            if missing := lr.async_get_missing_label_ids(hass, settings["labels"]):
                raise HomeAssistantError(
                    f"Labels not found: {', '.join(sorted(missing))}"
                )
        if settings.get("disabled_by"):
            settings["disabled_by"] = er.RegistryEntryDisabler.USER
        if settings.get("hidden_by"):
            settings["hidden_by"] = er.RegistryEntryHider.USER
        if "aliases" in settings:
            settings["aliases"] = [
                er.COMPUTED_NAME if alias is None else alias
                for alias in settings["aliases"]
            ]

        was_disabled = entry.disabled_by is not None
        try:
            entry = er.async_get(hass).async_update_entity(entity_id, **settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        result = _format_entity_settings(hass, entry)
        if was_disabled and entry.disabled_by is None:
            # The integration adds an enabled entity only when its config entry reloads
            if not (config_entry_id := entry.config_entry_id) or (
                (config_entry := hass.config_entries.async_get_entry(config_entry_id))
                and not config_entry.supports_unload
            ):
                result["note"] = "Home Assistant must restart to add the entity."
            else:
                result["note"] = (
                    "The integration reloads in "
                    f"{config_entries.RELOAD_AFTER_UPDATE_DELAY} seconds to add "
                    "the entity."
                )
        return ToolResult(data={"result": result})


class RemoveEntityTool(Tool):
    """LLM Tool to remove an entity that its integration no longer provides."""

    name = "config__remove_entity"
    title = "Remove entity"
    description = (
        "Remove an entity that its integration no longer provides, like the entity "
        "of a removed device. To stop using an entity that is still provided, "
        "disable it with config__update_entity_settings."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("entity_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Remove the entity."""
        entity_id = self.parameters(tool_input.tool_args)["entity_id"]
        _get_entity_entry(hass, entity_id)
        # Like the UI, only a restored state shows that the integration no longer
        # provides the entity. A disabled entity has no state at all.
        if (state := hass.states.get(entity_id)) is None or not state.attributes.get(
            ATTR_RESTORED
        ):
            raise HomeAssistantError(
                f"Entity '{entity_id}' is still provided by its integration, or is "
                "disabled. Only entities that their integration no longer provides "
                "can be removed."
            )
        er.async_get(hass).async_remove(entity_id)
        return ToolResult(data={"result": {"entity_id": entity_id}})


def _get_floor(hass: HomeAssistant, floor_id: str) -> fr.FloorEntry:
    """Return a floor."""
    if (floor := fr.async_get(hass).async_get_floor(floor_id)) is None:
        raise HomeAssistantError(f"Floor '{floor_id}' not found.")
    return floor


def _format_floor_settings(floor: fr.FloorEntry) -> JsonObjectType:
    """Format the settings of a floor for LLM consumption."""
    return {
        "floor_id": floor.floor_id,
        "name": floor.name,
        "aliases": list[JsonValueType](sorted(floor.aliases)),
        "icon": floor.icon,
        "level": floor.level,
    }


_FLOOR_SETTINGS = {
    probatio.Optional(
        "aliases",
        description=(
            "Other names that voice assistants know the floor by. This replaces "
            "all aliases."
        ),
    ): [_NON_EMPTY_STRING],
    probatio.Optional(
        "icon", description="The icon, like 'mdi:home-floor-1'. null removes it."
    ): probatio.Any(None, probatio.All(str, cv.icon)),
    probatio.Optional(
        "level",
        description=(
            "The level of the floor, to sort floors. 0 is the ground floor, -1 the "
            "floor below it. null removes it."
        ),
    ): probatio.Any(None, int),
}


class GetFloorSettingsTool(Tool):
    """LLM Tool to get the settings of a floor."""

    name = "config__get_floor_settings"
    title = "Get floor settings"
    description = (
        "Get the settings of the floor with the given floor_id. Use search__search "
        "to find the floor_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("floor_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the settings of the floor."""
        args = self.parameters(tool_input.tool_args)
        floor = _get_floor(hass, args["floor_id"])
        return ToolResult(data={"result": _format_floor_settings(floor)})


class UpdateFloorSettingsTool(Tool):
    """LLM Tool to update the settings of a floor."""

    name = "config__update_floor_settings"
    title = "Update floor settings"
    description = (
        "Update the settings of the floor with the given floor_id. Only the given "
        "settings change. Returns the new settings."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required("floor_id"): _NON_EMPTY_STRING,
            probatio.Optional("name"): _NON_EMPTY_STRING,
            **_FLOOR_SETTINGS,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the settings of the floor and return the new settings."""
        settings = self.parameters(tool_input.tool_args)
        floor_id = settings.pop("floor_id")
        _get_floor(hass, floor_id)
        if "aliases" in settings:
            settings["aliases"] = set(settings["aliases"])
        try:
            floor = fr.async_get(hass).async_update(floor_id, **settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return ToolResult(data={"result": _format_floor_settings(floor)})


class CreateFloorTool(Tool):
    """LLM Tool to create a floor."""

    name = "config__create_floor"
    title = "Create floor"
    description = "Create a floor. Returns the settings of the new floor."
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {probatio.Required("name"): _NON_EMPTY_STRING, **_FLOOR_SETTINGS}
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Create the floor and return its settings."""
        settings = self.parameters(tool_input.tool_args)
        if "aliases" in settings:
            settings["aliases"] = set(settings["aliases"])
        try:
            floor = fr.async_get(hass).async_create(**settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return ToolResult(data={"result": _format_floor_settings(floor)})


class DeleteFloorTool(Tool):
    """LLM Tool to delete a floor."""

    name = "config__delete_floor"
    title = "Delete floor"
    description = (
        "Delete the floor with the given floor_id. Its areas stay, without a floor."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("floor_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Delete the floor."""
        floor_id = self.parameters(tool_input.tool_args)["floor_id"]
        _get_floor(hass, floor_id)
        fr.async_get(hass).async_delete(floor_id)
        return ToolResult(data={"result": {"floor_id": floor_id}})


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
            StartFlowTool(),
            ConfigureFlowTool(),
            GetCoreConfigTool(),
            UpdateCoreConfigTool(),
            GetEntitySettingsTool(),
            UpdateEntitySettingsTool(),
            RemoveEntityTool(),
            GetFloorSettingsTool(),
            UpdateFloorSettingsTool(),
            CreateFloorTool(),
            DeleteFloorTool(),
        ]
    )
