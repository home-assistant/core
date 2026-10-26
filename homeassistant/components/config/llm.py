"""LLM tools for the config integration."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import suppress
import re
from typing import Any, override

import probatio

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import DependencyError, HomeAssistantError
from homeassistant.helpers import config_validation as cv, translation
from homeassistant.helpers.llm import (
    LLM_API_HOME_ASSISTANT,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN

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


def _format_short_id(domain: str, target_id: str, all_ids: Iterable[str]) -> str:
    """Format target_id as a unique '<domain>:<suffix>' ID among all_ids."""
    others = [item_id for item_id in all_ids if item_id != target_id]
    length = _MIN_SHORT_ID_LEN
    while any(other.endswith(target_id[-length:]) for other in others):
        length += 1
    return f"{domain}:{target_id[-length:]}"


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


def _parse_short_id(short_id: str, label: str) -> tuple[str, str]:
    """Parse and validate a '<domain>:<suffix>' short ID."""
    domain, sep, suffix = short_id.partition(":")
    if not sep or not domain or len(suffix) < _MIN_SHORT_ID_LEN:
        raise HomeAssistantError(f"{label} '{short_id}' not found.")
    return domain.lower(), suffix


def _resolve_short_entry_id(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    """Resolve a ConfigEntry from a '<domain>:<suffix>' short ID."""
    domain, suffix = _parse_short_id(entry_id, "Config entry")
    matches = [
        candidate
        for candidate in hass.config_entries.async_entries(domain)
        if candidate.entry_id.endswith(suffix)
    ]
    if len(matches) != 1:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")
    return matches[0]


def _format_short_flow_id(hass: HomeAssistant, domain: str, flow_id: str) -> str:
    """Format a flow_id as a short '<domain>:<suffix>' ID."""
    return _format_short_id(
        domain,
        flow_id,
        (
            flw["flow_id"]
            for flw in hass.config_entries.flow.async_progress_by_handler(domain)
        ),
    )


def _resolve_short_flow_id(
    hass: HomeAssistant, short_flow_id: str
) -> data_entry_flow.FlowHandler[Any, Any, Any]:
    """Resolve an active config flow from a '<domain>:<suffix>' short ID."""
    domain, suffix = _parse_short_id(short_flow_id, "Flow")
    flow_mgr = hass.config_entries.flow
    matches = [
        flw
        for progress in flow_mgr.async_progress_by_handler(domain)
        if progress["flow_id"].endswith(suffix)
        and (flw := flow_mgr._progress.get(progress["flow_id"])) is not None  # noqa: SLF001
        and flw.cur_step is not None
    ]
    if len(matches) != 1:
        raise HomeAssistantError(f"Flow '{short_flow_id}' not found.")
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


def _enrich_schema_fields(
    fields: list[dict[str, Any]],
    trans: dict[str, str],
    prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> list[JsonValueType]:
    """Enrich probatio.to_field_list items with resolved translations."""
    enriched: list[JsonValueType] = []
    for raw_field in fields:
        field: dict[str, Any] = dict(raw_field)
        name: str = field["name"]

        if isinstance(desc_meta := field.get("description"), dict):
            field.pop("description")
            if (suggested_value := desc_meta.get("suggested_value")) is not None:
                field["suggested_value"] = suggested_value

        if field.get("type") == "expandable" and isinstance(
            nested_schema := field.get("schema"), list
        ):
            sec_prefix = f"{prefix}.sections.{name}"
            label_key, desc_key = f"{sec_prefix}.name", f"{sec_prefix}.description"
            field["schema"] = _enrich_schema_fields(
                nested_schema, trans, sec_prefix, placeholders
            )
        else:
            label_key, desc_key = (
                f"{prefix}.data.{name}",
                f"{prefix}.data_description.{name}",
            )

        if label := _interpolate_placeholders(trans.get(label_key), placeholders):
            field["label"] = label
        if description := _interpolate_placeholders(trans.get(desc_key), placeholders):
            field["description"] = description

        enriched.append(field)
    return enriched


def _format_menu_options(
    raw_menu_options: Any,
    trans: dict[str, str],
    step_prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> JsonObjectType:
    """Format and translate menu_options for a MENU flow step."""
    menu_options_out: JsonObjectType = {}
    if not isinstance(raw_menu_options, Iterable):
        return menu_options_out
    for opt in raw_menu_options:
        fallback = (
            raw_menu_options[opt] if isinstance(raw_menu_options, Mapping) else opt
        )
        label = trans.get(f"{step_prefix}.menu_options.{opt}") or fallback
        opt_desc = trans.get(f"{step_prefix}.menu_option_descriptions.{opt}")
        label_str = _interpolate_placeholders(label, placeholders) or opt
        if opt_desc_str := _interpolate_placeholders(opt_desc, placeholders):
            menu_options_out[opt] = {"label": label_str, "description": opt_desc_str}
        else:
            menu_options_out[opt] = label_str
    return menu_options_out


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
    result: data_entry_flow.FlowResult[Any, Any],
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
        "flow_id": _format_short_flow_id(hass, domain, result["flow_id"]),
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
            if (schema := result.get("data_schema")) is not None and isinstance(
                serialized := probatio.to_field_list(
                    schema, custom_serializer=cv.custom_serializer
                ),
                list,
            ):
                raw_fields = serialized
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
            formatted["menu_options"] = _format_menu_options(
                result.get("menu_options", []), trans, step_prefix, placeholders
            )
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
        if isinstance(created_entry := result.get("result"), ConfigEntry):
            formatted["entry_id"] = _format_short_id(
                created_entry.domain,
                created_entry.entry_id,
                (
                    entry.entry_id
                    for entry in hass.config_entries.async_entries(created_entry.domain)
                ),
            )

    elif flow_type is data_entry_flow.FlowResultType.ABORT:
        reason = result["reason"]
        formatted["reason"] = reason
        abort_msg = trans.get(f"{base_prefix}.abort.{reason}") or trans.get(
            f"component.homeassistant.config.abort.{reason}"
        )
        if abort_text := _interpolate_placeholders(abort_msg, placeholders):
            formatted["description"] = abort_text

    return ToolResult(data={"result": formatted})


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

        entries = hass.config_entries.async_entries()

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
            ): _NON_EMPTY_STRING,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Start the requested config flow and return its formatted initial step."""
        args = self.parameters(tool_input.tool_args)
        domain: str = args["domain"].lower()
        try:
            result = await hass.config_entries.flow.async_init(
                domain,
                context={"source": config_entries.SOURCE_USER},
            )
        except data_entry_flow.UnknownHandler:
            return _error_result(
                f"Integration '{domain}' does not exist or does not support config flows."
            )
        except DependencyError as err:
            return _error_result(
                f"Failed dependencies: {', '.join(err.failed_dependencies)}"
            )
        except HomeAssistantError as err:
            return _error_result(str(err))

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
        assert cur_step is not None
        domain = str(flow_handler.handler)
        canonical_short_id = _format_short_flow_id(hass, domain, flow_id)

        if abort:
            flow_mgr.async_abort(flow_id)
            return ToolResult(
                data={
                    "result": {
                        "flow_id": canonical_short_id,
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
                return ToolResult(
                    data={
                        "result": {
                            "flow_id": canonical_short_id,
                            "type": str(cur_type),
                            "step_id": str(cur_step.get("step_id", "user")),
                            "errors": err.schema_errors,
                        }
                    },
                    error=True,
                )
            except data_entry_flow.UnknownFlow:
                return _error_result(f"Flow '{short_flow_id}' not found.")
            except HomeAssistantError as err:
                return _error_result(str(err))

        return await _async_finalize_flow_step(
            hass, result, domain, llm_context.language
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
            StartFlowTool(),
            ConfigureFlowTool(),
        ]
    )
