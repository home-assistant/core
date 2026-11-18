"""LLM tools for the config integration."""

from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
import heapq
import re
from typing import TYPE_CHECKING, Any, override

import probatio

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlowResult
from homeassistant.const import ATTR_RESTORED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import DependencyError, HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
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
_DOMAIN_STRING = probatio.All(str, probatio.Strip, probatio.Lower, probatio.NonEmpty())
_MIN_SHORT_ID_LEN = 4
_OAUTH_RUNTIME_ERRORS = ("No current request in context", "No header in request")


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
    - 1: all query words match domain or name
    - 2: all query words match domain, name, or brand
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
        seen.add(domain)
        if query in (domain, name_f):
            rank = 0
        elif all(word in head for word in words):
            rank = 1
        else:
            rank = 2
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
) -> data_entry_flow.FlowHandler[Any, Any, Any]:
    """Resolve an active config flow from a '<domain>:<suffix>' short ID."""
    domain, sep, suffix = flow_id.partition(":")
    if not sep or not domain or len(suffix) < _MIN_SHORT_ID_LEN:
        raise HomeAssistantError(f"Flow '{flow_id}' not found.")

    flow_mgr = hass.config_entries.flow
    matches = [
        flow_mgr._progress[flw["flow_id"]]  # noqa: SLF001
        for flw in flow_mgr.async_progress_by_handler(domain)
        if flw["flow_id"].endswith(suffix)
    ]
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


def _build_external_step_error(domain: str) -> ToolResult:
    """Return an error ToolResult directing the user to complete OAuth/external setup in the UI."""
    frontend_url = f"/config/integrations/dashboard/add?domain={domain}"
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
    result: ConfigFlowResult,
    domain: str,
    language: str | None,
) -> ToolResult:
    """Handle external/OAuth steps or format a DataEntryFlow result with translations."""
    flow_type = result["type"]
    if (
        flow_type is data_entry_flow.FlowResultType.EXTERNAL_STEP
        or result.get("step_id") == "pick_implementation"
    ):
        with suppress(data_entry_flow.UnknownFlow):
            hass.config_entries.flow.async_abort(result["flow_id"])
        return _build_external_step_error(domain)
    if (
        flow_type is data_entry_flow.FlowResultType.ABORT
        and result.get("reason") == "missing_credentials"
    ):
        return _build_external_step_error(domain)

    lang = _resolve_language(hass, language)
    trans_domain: str = result.get("translation_domain") or domain
    trans = await translation.async_get_translations(
        hass, lang, "config", {domain, trans_domain, "homeassistant"}
    )
    title_trans = await translation.async_get_translations(
        hass, lang, "title", {domain}
    )
    base_prefix = f"component.{trans_domain}.config"
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
        abort_msg = trans.get(f"{base_prefix}.abort.{reason}") or trans.get(
            f"component.homeassistant.config.abort.{reason}"
        )
        if abort_text := _interpolate_placeholders(abort_msg, placeholders):
            formatted["description"] = abort_text

    return ToolResult(data={"result": formatted})


# Only user-initiated config flows are exposed here for now. Listing background
# discovery/reauth flows in progress, as well as starting options, reconfigure,
# and subentry flows on existing entries, are omitted for now.
class StartFlowTool(Tool):
    """LLM Tool to start a new configuration flow."""

    name = "config__start_flow"
    title = "Start configuration flow"
    description = (
        "Start a configuration flow to set up a new integration or helper instance "
        "in Home Assistant and return its initial step."
    )
    annotations = ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=True
    )
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "domain",
                description="Integration domain to set up (e.g. 'local_todo', 'template').",
            ): _DOMAIN_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Start the requested config flow and return its formatted initial step."""
        args = self.parameters(tool_input.tool_args)
        domain: str = args["domain"]
        flow_mgr = hass.config_entries.flow
        context: config_entries.ConfigFlowContext = {
            "source": config_entries.SOURCE_USER
        }
        try:
            result = await flow_mgr.async_init(domain, context=context)
        except data_entry_flow.UnknownHandler:
            return _error_result(
                f"Integration '{domain}' does not exist or does not support config flows."
            )
        except DependencyError as err:
            return _error_result(
                f"Failed dependencies: {', '.join(err.failed_dependencies)}"
            )
        except RuntimeError as err:
            if str(err) not in _OAUTH_RUNTIME_ERRORS:
                raise
            for flw in flow_mgr.async_progress_by_handler(
                domain, include_uninitialized=True
            ):
                if flw["context"] is context:
                    flow_mgr.async_abort(flw["flow_id"])
            return _build_external_step_error(domain)

        return await _async_finalize_flow_step(
            hass, result, domain, llm_context.language
        )


class ConfigureFlowTool(Tool):
    """LLM Tool to inspect, advance, or abort an in-progress config flow."""

    name = "config__configure_flow"
    title = "Configure flow step"
    description = (
        "Inspect, submit input to, or abort an in-progress configuration flow by flow_id.\n"
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

        flow_mgr = hass.config_entries.flow
        flow_id = flow_handler.flow_id
        cur_step = flow_handler.cur_step
        if TYPE_CHECKING:
            assert cur_step is not None
        domain = str(flow_handler.handler)

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
                return _build_external_step_error(domain)

        return await _async_finalize_flow_step(
            hass, result, domain, llm_context.language
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class _RegistrySettings:
    """The settings of a registry, for the generic registry settings tools.

    The functions raise HomeAssistantError with a message for the LLM.
    """

    name: str
    id_key: str
    settings: dict[probatio.Marker, Any]
    remove_description: str
    get: Callable[[HomeAssistant, str], JsonObjectType]
    update: Callable[[HomeAssistant, str, dict[str, Any]], JsonObjectType]
    remove: Callable[[HomeAssistant, str], None]


class GetRegistrySettingsTool(Tool):
    """LLM Tool to get the settings of a registry item."""

    annotations = ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    integration = DOMAIN

    def __init__(self, registry: _RegistrySettings) -> None:
        """Init the tool."""
        self._registry = registry
        self.name = f"config__get_{registry.name}_settings"
        self.title = f"Get {registry.name} settings"
        self.description = (
            f"Get the settings of the {registry.name} with the given "
            f"{registry.id_key}. Use search__search to find the {registry.id_key}."
        )
        self.parameters = probatio.Schema(
            {probatio.Required(registry.id_key): _NON_EMPTY_STRING}
        )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Get the settings."""
        args = self.parameters(tool_input.tool_args)
        try:
            result = self._registry.get(hass, args[self._registry.id_key])
        except HomeAssistantError as err:
            return _error_result(str(err))
        return ToolResult(data={"result": result})


class UpdateRegistrySettingsTool(Tool):
    """LLM Tool to update the settings of a registry item."""

    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN

    def __init__(self, registry: _RegistrySettings) -> None:
        """Init the tool."""
        self._registry = registry
        self.name = f"config__update_{registry.name}_settings"
        self.title = f"Update {registry.name} settings"
        self.description = (
            f"Update the settings of the {registry.name} with the given "
            f"{registry.id_key}. Only the given settings change. Returns the new "
            "settings."
        )
        self.parameters = probatio.Schema(
            {
                probatio.Required(registry.id_key): _NON_EMPTY_STRING,
                **registry.settings,
            }
        )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Update the settings."""
        args = self.parameters(tool_input.tool_args)
        item_id = args.pop(self._registry.id_key)
        try:
            result = self._registry.update(hass, item_id, args)
        except HomeAssistantError as err:
            return _error_result(str(err))
        return ToolResult(data={"result": result})


class RemoveRegistryItemTool(Tool):
    """LLM Tool to remove a registry item."""

    annotations = ToolAnnotations(
        read_only=False, destructive=True, idempotent=True, open_world=False
    )
    integration = DOMAIN

    def __init__(self, registry: _RegistrySettings) -> None:
        """Init the tool."""
        self._registry = registry
        self.name = f"config__remove_{registry.name}"
        self.title = f"Remove {registry.name}"
        self.description = registry.remove_description
        self.parameters = probatio.Schema(
            {probatio.Required(registry.id_key): _NON_EMPTY_STRING}
        )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Remove the item."""
        args = self.parameters(tool_input.tool_args)
        item_id = args[self._registry.id_key]
        try:
            self._registry.remove(hass, item_id)
        except HomeAssistantError as err:
            return _error_result(str(err))
        return ToolResult(data={"result": {self._registry.id_key: item_id}})


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


@callback
def _get_entity_settings(hass: HomeAssistant, entity_id: str) -> JsonObjectType:
    """Return the settings of an entity."""
    return _format_entity_settings(hass, _get_entity_entry(hass, entity_id))


@callback
def _update_entity_settings(
    hass: HomeAssistant, entity_id: str, settings: dict[str, Any]
) -> JsonObjectType:
    """Update the settings of an entity and return the new settings."""
    entry = _get_entity_entry(hass, entity_id)
    if (area_id := settings.get("area_id")) and ar.async_get(hass).async_get_area(
        area_id
    ) is None:
        raise HomeAssistantError(f"Area '{area_id}' not found.")
    if "labels" in settings:
        settings["labels"] = set(settings["labels"])
        if missing := lr.async_get_missing_label_ids(hass, settings["labels"]):
            raise HomeAssistantError(f"Labels not found: {', '.join(sorted(missing))}")
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
                f"{config_entries.RELOAD_AFTER_UPDATE_DELAY} seconds to add the "
                "entity."
            )
    return result


@callback
def _remove_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Remove an entity that its integration no longer provides."""
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


_NULLABLE_STRING = probatio.Any(None, _NON_EMPTY_STRING)

_ENTITY_REGISTRY = _RegistrySettings(
    name="entity",
    id_key="entity_id",
    settings={
        probatio.Optional(
            "name",
            description=(
                "The name of the entity. null uses the name from the integration."
            ),
        ): _NULLABLE_STRING,
        probatio.Optional(
            "icon",
            description=(
                "The icon, like 'mdi:lamp'. null uses the icon from the integration."
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
                "'user' disables the entity, null enables it. A disabled entity "
                "has no state."
            ),
        ): probatio.Any(None, er.RegistryEntryDisabler.USER.value),
        probatio.Optional(
            "hidden_by",
            description=(
                "'user' hides the entity from auto-populated dashboards, null shows it."
            ),
        ): probatio.Any(None, er.RegistryEntryHider.USER.value),
        probatio.Optional(
            "aliases",
            description=(
                "The names that voice assistants know the entity by. This replaces "
                "all aliases. null stands for the name of the entity."
            ),
        ): [_NULLABLE_STRING],
        probatio.Optional(
            "labels",
            description="The label_ids. This replaces all labels.",
        ): [_NON_EMPTY_STRING],
    },
    remove_description=(
        "Remove an entity that its integration no longer provides, like the entity "
        "of a removed device. To stop using an entity that is still provided, "
        "disable it with config__update_entity_settings."
    ),
    get=_get_entity_settings,
    update=_update_entity_settings,
    remove=_remove_entity,
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
            StartFlowTool(),
            ConfigureFlowTool(),
            GetRegistrySettingsTool(_ENTITY_REGISTRY),
            UpdateRegistrySettingsTool(_ENTITY_REGISTRY),
            RemoveRegistryItemTool(_ENTITY_REGISTRY),
        ]
    )
