"""LLM tools for the config integration."""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from contextlib import suppress
import heapq
import re
from typing import TYPE_CHECKING, Any, Literal, cast, override

import probatio

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import DependencyError, HomeAssistantError
from homeassistant.generated.integration_categories import INTEGRATION_CATEGORIES
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
    translation,
)
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import VolDictType
from homeassistant.loader import (
    IntegrationNotFound,
    async_get_integration,
    async_get_integration_descriptions,
)
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN, SUPPORTED_LABEL_THEME_COLORS
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
_MIN_SHORT_ID_LEN = 4
_OAUTH_RUNTIME_ERRORS = ("No current request in context", "No header in request")
type _FlowCategory = Literal["config", "options"]
_FLOW_TYPES = ["config", "options", "reconfigure"]
_UPDATE_CORE_CONFIG_SCHEMA = probatio.Schema(UPDATE_CONFIG_SCHEMA)


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
        for candidate in hass.config_entries.async_entries(domain)
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
    if entry.state is ConfigEntryState.LOADED and entry.supports_options:
        result["supports_options"] = True
    if (
        entry.disabled_by is None
        and entry.source != config_entries.SOURCE_IGNORE
        and entry.supports_reconfigure
    ):
        result["supports_reconfigure"] = True
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
        "find entry_ids and supported flow capabilities (supports_options, "
        "supports_reconfigure)."
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


_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


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


def _resolve_short_flow_id(
    hass: HomeAssistant, flow_id: str
) -> ConfigFlow | OptionsFlow:
    """Resolve an active config or options flow from a '<domain>:<suffix>' short ID."""
    domain, sep, suffix = flow_id.partition(":")
    if not sep or not domain or len(suffix) < _MIN_SHORT_ID_LEN:
        raise HomeAssistantError(f"Flow '{flow_id}' not found.")

    flow_mgr = hass.config_entries.flow
    matches: list[ConfigFlow | OptionsFlow] = [
        cast(ConfigFlow, flow_mgr._progress[flw["flow_id"]])  # noqa: SLF001
        for flw in flow_mgr.async_progress_by_handler(domain)
        if flw["flow_id"].endswith(suffix)
    ]

    options_mgr = hass.config_entries.options
    for entry in hass.config_entries.async_entries(domain):
        matches.extend(
            cast(OptionsFlow, options_mgr._progress[flw["flow_id"]])  # noqa: SLF001
            for flw in options_mgr.async_progress_by_handler(entry.entry_id)
            if flw["flow_id"].endswith(suffix)
        )

    if len(matches) != 1:
        raise HomeAssistantError(f"Flow '{flow_id}' not found.")

    return matches[0]


def _enrich_schema_fields(
    fields: list[dict[str, Any]],
    trans: dict[str, str],
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
            _enrich_schema_fields(field["schema"], trans, sec_prefix, placeholders)
        else:
            label_key, desc_key = (
                f"{prefix}.data.{name}",
                f"{prefix}.data_description.{name}",
            )

        if label := _interpolate_placeholders(trans.get(label_key), placeholders):
            field["label"] = label
        if description := _interpolate_placeholders(trans.get(desc_key), placeholders):
            field["description"] = description

    return fields  # type: ignore[return-value]


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
    result: ConfigFlowResult,
    domain: str,
    language: str | None,
    *,
    flow_category: _FlowCategory = "config",
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
    base_prefix = f"component.{trans_domain}.{flow_category}"
    placeholders: Mapping[str, Any] | None = result.get("description_placeholders")
    formatted: JsonObjectType = {
        "flow_id": f"{domain}:{result['flow_id'][-_MIN_SHORT_ID_LEN:]}",
        "type": str(flow_type),
    }

    if (step_id := result.get("step_id")) is not None:
        formatted["step_id"] = step_id
        step_prefix = f"{base_prefix}.step.{step_id}"
        if title := _interpolate_placeholders(
            trans.get(f"{step_prefix}.title")
            or title_trans.get(f"component.{domain}.title"),
            placeholders,
        ):
            formatted["title"] = title
        if description := _interpolate_placeholders(
            trans.get(f"{step_prefix}.description"), placeholders
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
                raw_fields, trans, step_prefix, placeholders
            )
            if err_source := result.get("errors"):
                formatted["errors"] = {
                    err_field: (
                        _interpolate_placeholders(
                            trans.get(f"{base_prefix}.error.{err_val}", err_val),
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
                    _interpolate_placeholders(
                        trans.get(f"{step_prefix}.menu_options.{opt}")
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
            if description := _interpolate_placeholders(
                trans.get(f"{base_prefix}.progress.{progress_action}"), placeholders
            ):
                formatted["description"] = description

    elif flow_type is data_entry_flow.FlowResultType.CREATE_ENTRY:
        if title := result.get("title"):
            formatted["title"] = title
        desc_key = result.get("description") or "default"
        if desc := _interpolate_placeholders(
            trans.get(f"{base_prefix}.create_entry.{desc_key}"), placeholders
        ):
            formatted["description"] = desc
        if (created_entry := result.get("result")) is not None:
            formatted["entry_id"] = _format_short_entry_ids(
                hass.config_entries.async_entries(created_entry.domain)
            )[created_entry.entry_id]

    elif flow_type is data_entry_flow.FlowResultType.ABORT:
        reason = result["reason"]
        formatted["reason"] = reason
        abort_msg = trans.get(f"{base_prefix}.abort.{reason}")
        if not abort_msg:
            if flow_category != "config":
                trans = await translation.async_get_translations(
                    hass, lang, "config", {"homeassistant"}
                )
            abort_msg = trans.get(f"component.homeassistant.config.abort.{reason}")
        if abort_text := _interpolate_placeholders(abort_msg, placeholders):
            formatted["description"] = abort_text

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
                "flow_id": f"{handler}:{flw['flow_id'][-_MIN_SHORT_ID_LEN:]}",
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


# Starting subentry flows on existing entries is not supported.
class StartFlowTool(Tool):
    """LLM Tool to start a configuration, options, or reconfigure flow."""

    name = "config__start_flow"
    title = "Start configuration flow"
    description = (
        "Start a configuration, options, or reconfigure flow in Home Assistant and "
        "return its initial step.\n"
        "- 'config' (default): set up a new integration or helper instance by 'domain'.\n"
        "- 'options': update runtime options on a loaded config entry by 'entry_id' "
        "(requires supports_options).\n"
        "- 'reconfigure': update connection or authentication settings on an existing "
        "config entry by 'entry_id' (requires supports_reconfigure)."
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
                    "'options', or 'reconfigure'."
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
                    "The entry_id of the config entry when flow_type is 'options' "
                    "or 'reconfigure' (e.g. 'hue:8K2M')."
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

        if domain is not None and entry_id is not None:
            return _error_result("Cannot specify both 'domain' and 'entry_id'.")

        flow_mgr: data_entry_flow.FlowManager[Any, Any, Any]
        if flow_type == "config":
            if entry_id is not None:
                return _error_result(
                    "Specify 'flow_type' ('options' or 'reconfigure') when passing "
                    "'entry_id'."
                )
            if domain is None:
                return _error_result("'domain' is required when flow_type is 'config'.")
            flow_mgr = hass.config_entries.flow
            handler = domain
            target_domain = domain
            context: config_entries.ConfigFlowContext = {
                "source": config_entries.SOURCE_USER
            }
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
            unsupported_msg = f"Config entry '{entry_id}' does not support {flow_type}."
            if flow_type == "options":
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
                context = {}
            else:
                flow_mgr = hass.config_entries.flow
                handler = entry.domain
                context = {
                    "source": config_entries.SOURCE_RECONFIGURE,
                    "entry_id": entry.entry_id,
                }

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
            flow_category="options" if flow_type == "options" else "config",
            is_new_entry=is_new_entry,
        )


class ConfigureFlowTool(Tool):
    """LLM Tool to inspect, advance, or abort an in-progress flow."""

    name = "config__configure_flow"
    title = "Configure flow step"
    description = (
        "Inspect, submit input to, or abort an in-progress configuration, options, "
        "or reconfigure flow by flow_id.\n"
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

        if user_input is not None and next_step_id is not None:
            return _error_result("Cannot specify both 'user_input' and 'next_step_id'.")
        if user_input is not None and "next_step_id" in user_input:
            return _error_result(
                "Use the 'next_step_id' parameter instead of 'user_input' "
                "to select a menu option."
            )

        try:
            flow_handler = _resolve_short_flow_id(hass, short_flow_id)
        except HomeAssistantError as err:
            return _error_result(str(err))

        if isinstance(flow_handler, OptionsFlow):
            flow_mgr: data_entry_flow.FlowManager[Any, Any] = (
                hass.config_entries.options
            )
            domain = flow_handler.config_entry.domain
            flow_category: _FlowCategory = "options"
            is_new_entry = False
        else:
            flow_mgr = hass.config_entries.flow
            domain = flow_handler.handler
            flow_category = "config"
            is_new_entry = flow_handler.context.get("source") not in (
                config_entries.SOURCE_REAUTH,
                config_entries.SOURCE_RECONFIGURE,
            )

        flow_id = flow_handler.flow_id
        cur_step = flow_handler.cur_step
        if TYPE_CHECKING:
            assert cur_step is not None

        if abort:
            flow_mgr.async_abort(flow_id)
            return ToolResult(
                data={
                    "result": {
                        "flow_id": short_flow_id,
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
            cur_type is data_entry_flow.FlowResultType.SHOW_PROGRESS
            and (progress_task := flow_handler.async_get_progress_task()) is not None
            and not progress_task.done()
        ):
            result = cur_step
        else:
            flow_input: dict[str, Any] | None = (
                {"next_step_id": next_step_id}
                if next_step_id is not None
                else user_input
            )
            try:
                result = await flow_mgr.async_configure(flow_id, flow_input)
            except data_entry_flow.InvalidData as err:
                return _error_result(f"Invalid input: {err.schema_errors}")
            except RuntimeError as err:
                if str(err) not in _OAUTH_RUNTIME_ERRORS:
                    raise
                flow_mgr.async_abort(flow_id)
                return _build_external_step_error(domain, is_new_entry=is_new_entry)

        return await _async_finalize_flow_step(
            hass,
            flow_mgr,
            result,
            domain,
            llm_context.language,
            flow_category=flow_category,
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


def _get_area_entry(hass: HomeAssistant, area_id: str) -> ar.AreaEntry:
    """Return the registry entry of an area."""
    if (area := ar.async_get(hass).async_get_area(area_id)) is None:
        raise HomeAssistantError(f"Area '{area_id}' not found.")
    return area


def _format_area_settings(area: ar.AreaEntry) -> JsonObjectType:
    """Format the settings of an area for LLM consumption."""
    return {
        "area_id": area.id,
        "name": area.name,
        "aliases": list[JsonValueType](sorted(area.aliases)),
        "floor_id": area.floor_id,
        "icon": area.icon,
        "labels": list[JsonValueType](sorted(area.labels)),
        "temperature_entity_id": area.temperature_entity_id,
        "humidity_entity_id": area.humidity_entity_id,
    }


def _prepare_area_settings(hass: HomeAssistant, settings: dict[str, Any]) -> None:
    """Check the floor and labels of the settings and convert the lists to sets."""
    if (floor_id := settings.get("floor_id")) and fr.async_get(hass).async_get_floor(
        floor_id
    ) is None:
        raise HomeAssistantError(f"Floor '{floor_id}' not found.")
    if "labels" in settings:
        settings["labels"] = set(settings["labels"])
        if missing := lr.async_get_missing_label_ids(hass, settings["labels"]):
            raise HomeAssistantError(f"Labels not found: {', '.join(sorted(missing))}")
    if "aliases" in settings:
        settings["aliases"] = set(settings["aliases"])


_AREA_SETTINGS: VolDictType = {
    probatio.Optional(
        "aliases",
        description=(
            "Other names that voice assistants know the area by. This replaces all "
            "aliases."
        ),
    ): [_NON_EMPTY_STRING],
    probatio.Optional(
        "floor_id", description="The floor_id. null removes the area from its floor."
    ): _NULLABLE_STRING,
    probatio.Optional(
        "icon", description="The icon, like 'mdi:sofa'. null removes the icon."
    ): probatio.Any(None, probatio.All(str, cv.icon)),
    probatio.Optional(
        "labels", description="The label_ids. This replaces all labels."
    ): [_NON_EMPTY_STRING],
    probatio.Optional(
        "temperature_entity_id",
        description=(
            "The sensor that gives the temperature of the area. null removes it."
        ),
    ): _NULLABLE_STRING,
    probatio.Optional(
        "humidity_entity_id",
        description="The sensor that gives the humidity of the area. null removes it.",
    ): _NULLABLE_STRING,
}


class GetAreaSettingsTool(Tool):
    """LLM Tool to get the settings of an area."""

    name = "config__get_area_settings"
    title = "Get area settings"
    description = (
        "Get the settings of the area with the given area_id. Use search__search "
        "to find the area_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("area_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the settings of the area."""
        args = self.parameters(tool_input.tool_args)
        area = _get_area_entry(hass, args["area_id"])
        return ToolResult(data={"result": _format_area_settings(area)})


class UpdateAreaSettingsTool(Tool):
    """LLM Tool to update the settings of an area."""

    name = "config__update_area_settings"
    title = "Update area settings"
    description = (
        "Update the settings of the area with the given area_id. Only the given "
        "settings change. Use search__search to find area_ids and label_ids. "
        "Returns the new settings."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required("area_id"): _NON_EMPTY_STRING,
            probatio.Optional("name"): _NON_EMPTY_STRING,
            **_AREA_SETTINGS,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the settings of the area and return the new settings."""
        settings = self.parameters(tool_input.tool_args)
        area_id = settings.pop("area_id")
        _get_area_entry(hass, area_id)
        _prepare_area_settings(hass, settings)
        try:
            area = ar.async_get(hass).async_update(area_id, **settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return ToolResult(data={"result": _format_area_settings(area)})


class CreateAreaTool(Tool):
    """LLM Tool to create an area."""

    name = "config__create_area"
    title = "Create area"
    description = (
        "Create an area, like a room. Use search__search to find label_ids. "
        "Returns the settings of the new area."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {probatio.Required("name"): _NON_EMPTY_STRING, **_AREA_SETTINGS}
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Create the area and return its settings."""
        settings = self.parameters(tool_input.tool_args)
        _prepare_area_settings(hass, settings)
        try:
            area = ar.async_get(hass).async_create(**settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return ToolResult(data={"result": _format_area_settings(area)})


class DeleteAreaTool(Tool):
    """LLM Tool to delete an area."""

    name = "config__delete_area"
    title = "Delete area"
    description = (
        "Delete the area with the given area_id. Its devices and entities stay, "
        "without an area."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("area_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Delete the area."""
        area_id = self.parameters(tool_input.tool_args)["area_id"]
        _get_area_entry(hass, area_id)
        ar.async_get(hass).async_delete(area_id)
        return ToolResult(data={"result": {"area_id": area_id}})


def _get_label_entry(hass: HomeAssistant, label_id: str) -> lr.LabelEntry:
    """Return the registry entry of a label."""
    if (entry := lr.async_get(hass).async_get_label(label_id)) is None:
        raise HomeAssistantError(f"Label '{label_id}' not found.")
    return entry


def _format_label_settings(entry: lr.LabelEntry) -> JsonObjectType:
    """Format the settings of a label for LLM consumption."""
    return {
        "label_id": entry.label_id,
        "name": entry.name,
        "color": entry.color,
        "icon": entry.icon,
        "description": entry.description,
    }


def _label_color(value: str) -> str:
    """Validate a theme color or a hex color."""
    if value in SUPPORTED_LABEL_THEME_COLORS:
        return value
    return cv.color_hex(value)


_LABEL_SETTINGS: VolDictType = {
    probatio.Optional(
        "color",
        description=(
            "A hex color like '#ff0000', or a theme color: "
            f"{', '.join(sorted(SUPPORTED_LABEL_THEME_COLORS))}. null removes it."
        ),
    ): probatio.Any(None, probatio.All(str, _label_color)),
    probatio.Optional(
        "icon", description="The icon, like 'mdi:tag'. null removes it."
    ): probatio.Any(None, probatio.All(str, cv.icon)),
    probatio.Optional(
        "description", description="What the label is for. null removes it."
    ): probatio.Any(None, str),
}


class GetLabelSettingsTool(Tool):
    """LLM Tool to get the settings of a label."""

    name = "config__get_label_settings"
    title = "Get label settings"
    description = (
        "Get the settings of the label with the given label_id. Use search__search "
        "to find the label_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("label_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the settings of the label."""
        args = self.parameters(tool_input.tool_args)
        entry = _get_label_entry(hass, args["label_id"])
        return ToolResult(data={"result": _format_label_settings(entry)})


class UpdateLabelSettingsTool(Tool):
    """LLM Tool to update the settings of a label."""

    name = "config__update_label_settings"
    title = "Update label settings"
    description = (
        "Update the settings of the label with the given label_id. Only the given "
        "settings change. Returns the new settings."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required("label_id"): _NON_EMPTY_STRING,
            probatio.Optional("name"): _NON_EMPTY_STRING,
            **_LABEL_SETTINGS,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the settings of the label and return the new settings."""
        settings = self.parameters(tool_input.tool_args)
        label_id = settings.pop("label_id")
        _get_label_entry(hass, label_id)
        try:
            entry = lr.async_get(hass).async_update(label_id, **settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return ToolResult(data={"result": _format_label_settings(entry)})


class CreateLabelTool(Tool):
    """LLM Tool to create a label."""

    name = "config__create_label"
    title = "Create label"
    description = "Create a label. Returns the settings of the new label."
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {probatio.Required("name"): _NON_EMPTY_STRING, **_LABEL_SETTINGS}
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Create the label and return its settings."""
        settings = self.parameters(tool_input.tool_args)
        try:
            entry = lr.async_get(hass).async_create(**settings)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return ToolResult(data={"result": _format_label_settings(entry)})


class DeleteLabelTool(Tool):
    """LLM Tool to delete a label."""

    name = "config__delete_label"
    title = "Delete label"
    description = (
        "Delete the label with the given label_id. It is removed from everything "
        "that has it."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("label_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Delete the label."""
        label_id = self.parameters(tool_input.tool_args)["label_id"]
        _get_label_entry(hass, label_id)
        lr.async_get(hass).async_delete(label_id)
        return ToolResult(data={"result": {"label_id": label_id}})


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


def _get_device_entry(hass: HomeAssistant, device_id: str) -> dr.AnyDeviceEntry:
    """Return the registry entry of a device."""
    if (
        device := dr.async_get(hass).async_get(
            device_id, include_composite_devices=False
        )
    ) is None:
        raise HomeAssistantError(f"Device '{device_id}' not found.")
    return device


def _format_device_settings(device: dr.AnyDeviceEntry) -> JsonObjectType:
    """Format the settings of a device for LLM consumption."""
    result: JsonObjectType = {
        "device_id": device.id,
        "name": device.name,
        "name_by_user": device.name_by_user,
        "area_id": device.area_id,
        "disabled_by": device.disabled_by,
        "labels": list[JsonValueType](sorted(device.labels)),
    }
    if isinstance(device, dr.ChildDeviceEntry):
        result["parent_device_id"] = device.parent_device_id
    else:
        result["manufacturer"] = device.manufacturer
        result["model"] = device.model
    return result


class GetDeviceSettingsTool(Tool):
    """LLM Tool to get the settings of a device."""

    name = "config__get_device_settings"
    title = "Get device settings"
    description = (
        "Get the settings of the device with the given device_id. Use "
        "search__search to find the device_id."
    )
    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema({probatio.Required("device_id"): _NON_EMPTY_STRING})

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return the settings of the device."""
        args = self.parameters(tool_input.tool_args)
        device = _get_device_entry(hass, args["device_id"])
        return ToolResult(data={"result": _format_device_settings(device)})


class UpdateDeviceSettingsTool(Tool):
    """LLM Tool to update the settings of a device."""

    name = "config__update_device_settings"
    title = "Update device settings"
    description = (
        "Update the settings of the device with the given device_id. Only the "
        "given settings change. Use search__search to find area and label IDs. "
        "Returns the new settings."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required("device_id"): _NON_EMPTY_STRING,
            probatio.Optional(
                "name_by_user",
                description=(
                    "The name of the device. null uses the name from the integration."
                ),
            ): _NULLABLE_STRING,
            probatio.Optional(
                "area_id", description="The area_id. null removes the area."
            ): _NULLABLE_STRING,
            probatio.Optional(
                "disabled_by",
                description=(
                    "'user' disables the device and its entities, null enables it."
                ),
            ): probatio.Any(None, dr.DeviceEntryDisabler.USER.value),
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
        """Update the settings of the device and return the new settings."""
        settings = self.parameters(tool_input.tool_args)
        device_id = settings.pop("device_id")
        device = _get_device_entry(hass, device_id)
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
            settings["disabled_by"] = dr.DeviceEntryDisabler.USER

        registry = dr.async_get(hass)
        enabling = (
            "disabled_by" in settings
            and settings["disabled_by"] is None
            and device.disabled_by is not None
        )
        if enabling:
            if (
                config_entry := hass.config_entries.async_get_entry(
                    device.config_entry_id
                )
            ) and config_entry.disabled_by:
                raise HomeAssistantError(
                    f"The config entry of device '{device_id}' is disabled. Enable "
                    "the config entry first."
                )
            if isinstance(device, dr.ChildDeviceEntry) and (
                (parent := registry.async_get(device.parent_device_id))
                and parent.disabled
            ):
                raise HomeAssistantError(
                    f"The parent device '{device.parent_device_id}' is disabled. "
                    "Enable the parent device first."
                )
        # Enabling the device enables these entities and the child devices that it
        # disabled, which reloads the integration
        device_ids = [device_id] + [
            child.id
            for child in dr.async_entries_for_parent_device(registry, device_id)
            if child.disabled_by is dr.DeviceEntryDisabler.DEVICE
        ]
        entities_to_enable = enabling and any(
            entity.disabled_by is er.RegistryEntryDisabler.DEVICE
            for enabled_device_id in device_ids
            for entity in er.async_entries_for_device(
                er.async_get(hass), enabled_device_id, include_disabled_entities=True
            )
        )
        updated: dr.AnyDeviceEntry | None
        if isinstance(device, dr.ChildDeviceEntry):
            updated = registry.async_update_child_device(device_id, **settings)
        else:
            updated = registry.async_update_device(device_id, **settings)
        if TYPE_CHECKING:
            assert updated is not None

        result = _format_device_settings(updated)
        if entities_to_enable and updated.disabled_by is None:
            if (
                config_entry := hass.config_entries.async_get_entry(
                    updated.config_entry_id
                )
            ) and not config_entry.supports_unload:
                result["note"] = "Home Assistant must restart to add the device."
            else:
                result["note"] = (
                    "The integration reloads in "
                    f"{config_entries.RELOAD_AFTER_UPDATE_DELAY} seconds to add "
                    "the device."
                )
        return ToolResult(data={"result": result})


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
            GetAreaSettingsTool(),
            UpdateAreaSettingsTool(),
            CreateAreaTool(),
            DeleteAreaTool(),
            GetLabelSettingsTool(),
            UpdateLabelSettingsTool(),
            CreateLabelTool(),
            DeleteLabelTool(),
            GetFloorSettingsTool(),
            UpdateFloorSettingsTool(),
            CreateFloorTool(),
            DeleteFloorTool(),
            GetDeviceSettingsTool(),
            UpdateDeviceSettingsTool(),
        ]
    )
