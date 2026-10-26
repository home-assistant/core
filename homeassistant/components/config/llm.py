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

_OAUTH_RUNTIME_ERRORS = {"No header in request", "No current request in context"}
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


def _enrich_select_options(
    options: list[Any],
    selector_trans: dict[str, str],
    domain: str,
    trans_domain: str,
    sel_trans_key: str,
) -> list[Any]:
    """Return a new options list with translated labels without mutating the source."""
    new_options: list[Any] = []
    for opt in options:
        opt_val = (
            opt
            if isinstance(opt, str)
            else opt.get("value")
            if isinstance(opt, dict)
            else None
        )
        if not isinstance(opt_val, str):
            new_options.append(opt)
            continue
        opt_label = selector_trans.get(
            f"component.{trans_domain}.selector.{sel_trans_key}.options.{opt_val}"
        ) or selector_trans.get(
            f"component.{domain}.selector.{sel_trans_key}.options.{opt_val}"
        )
        if isinstance(opt, str):
            new_options.append({"value": opt, "label": opt_label} if opt_label else opt)
        else:
            label = opt_label or opt.get("label")
            new_options.append({**opt, "label": label} if label else dict(opt))
    return new_options


def _enrich_schema_fields(
    fields: list[dict[str, Any]],
    trans: dict[str, str],
    selector_trans: dict[str, str],
    domain: str,
    trans_domain: str,
    prefix: str,
    trans_prefix: str,
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
            trans_sec_prefix = f"{trans_prefix}.sections.{name}"
            if sec_name := _interpolate_placeholders(
                trans.get(f"{trans_sec_prefix}.name")
                or trans.get(f"{sec_prefix}.name"),
                placeholders,
            ):
                field["label"] = sec_name
            if sec_desc := _interpolate_placeholders(
                trans.get(f"{trans_sec_prefix}.description")
                or trans.get(f"{sec_prefix}.description"),
                placeholders,
            ):
                field["description"] = sec_desc
            field["schema"] = _enrich_schema_fields(
                nested_schema,
                trans,
                selector_trans,
                domain,
                trans_domain,
                sec_prefix,
                trans_sec_prefix,
                placeholders,
            )
            enriched.append(field)
            continue

        if label := _interpolate_placeholders(
            trans.get(f"{trans_prefix}.data.{name}")
            or trans.get(f"{prefix}.data.{name}"),
            placeholders,
        ):
            field["label"] = label
        if description := _interpolate_placeholders(
            trans.get(f"{trans_prefix}.data_description.{name}")
            or trans.get(f"{prefix}.data_description.{name}"),
            placeholders,
        ):
            field["description"] = description

        if (
            isinstance(selector_cfg := field.get("selector"), dict)
            and isinstance(select_cfg := selector_cfg.get("select"), dict)
            and isinstance(options := select_cfg.get("options"), list)
        ):
            sel_trans_key = select_cfg.get("translation_key") or name
            field["selector"] = {
                **selector_cfg,
                "select": {
                    **select_cfg,
                    "options": _enrich_select_options(
                        options, selector_trans, domain, trans_domain, sel_trans_key
                    ),
                },
            }

        enriched.append(field)
    return enriched


def _resolve_step_title_and_description(
    formatted: JsonObjectType,
    trans: dict[str, str],
    title_trans: dict[str, str],
    domain: str,
    step_prefix: str,
    trans_step_prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> None:
    """Populate step title and description on a formatted flow step."""
    title = (
        trans.get(f"{trans_step_prefix}.title")
        or trans.get(f"{step_prefix}.title")
        or title_trans.get(f"component.{domain}.title")
    )
    if title := _interpolate_placeholders(title, placeholders):
        formatted["title"] = title

    description = trans.get(f"{trans_step_prefix}.description") or trans.get(
        f"{step_prefix}.description"
    )
    if description := _interpolate_placeholders(description, placeholders):
        formatted["description"] = description


def _translate_errors(
    errors: Mapping[str, Any],
    trans: dict[str, str],
    base_prefix: str,
    domain_prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> JsonObjectType:
    """Translate a dictionary of field error keys."""

    def _translate_one(err_val: Any) -> Any:
        if isinstance(err_val, str):
            err_msg = (
                trans.get(f"{base_prefix}.error.{err_val}")
                or trans.get(f"{domain_prefix}.error.{err_val}")
                or err_val
            )
            return _interpolate_placeholders(err_msg, placeholders) or err_val
        if isinstance(err_val, list):
            return [_translate_one(item) for item in err_val]
        return err_val

    return {err_field: _translate_one(err_val) for err_field, err_val in errors.items()}


async def _async_load_flow_translations(
    hass: HomeAssistant,
    domain: str,
    trans_domain: str,
    language: str | None,
) -> tuple[dict[str, str], str, str, str]:
    """Load config flow translations and construct translation key prefixes."""
    lang = _resolve_language(hass, language)
    trans = await translation.async_get_translations(
        hass, lang, "config", {domain, trans_domain, "homeassistant"}
    )
    base_prefix = f"component.{trans_domain}.config"
    domain_prefix = f"component.{domain}.config"
    return trans, base_prefix, domain_prefix, lang


def _format_form_step(
    formatted: JsonObjectType,
    result: data_entry_flow.FlowResult[Any, Any],
    trans: dict[str, str],
    title_trans: dict[str, str],
    selector_trans: dict[str, str],
    domain: str,
    trans_domain: str,
    base_prefix: str,
    domain_prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> None:
    """Populate fields and errors for a FORM flow result."""
    step_id = result["step_id"]
    formatted["step_id"] = step_id
    step_prefix = f"{domain_prefix}.step.{step_id}"
    trans_step_prefix = f"{base_prefix}.step.{step_id}"

    _resolve_step_title_and_description(
        formatted,
        trans,
        title_trans,
        domain,
        step_prefix,
        trans_step_prefix,
        placeholders,
    )
    if (last_step := result.get("last_step")) is not None:
        formatted["last_step"] = last_step

    schema = result.get("data_schema")
    serialized = (
        probatio.to_field_list(schema, custom_serializer=cv.custom_serializer)
        if schema is not None
        else []
    )
    raw_fields = serialized if isinstance(serialized, list) else []
    if schema is not None and raw_fields:
        data_entry_flow.add_visible_conditions_to_serialized_schema(schema, raw_fields)
    formatted["fields"] = _enrich_schema_fields(
        raw_fields,
        trans,
        selector_trans,
        domain,
        trans_domain,
        step_prefix,
        trans_step_prefix,
        placeholders,
    )

    if err_source := result.get("errors"):
        formatted["errors"] = _translate_errors(
            err_source,
            trans,
            base_prefix,
            domain_prefix,
            placeholders,
        )


def _format_menu_step(
    formatted: JsonObjectType,
    result: data_entry_flow.FlowResult[Any, Any],
    trans: dict[str, str],
    title_trans: dict[str, str],
    domain: str,
    base_prefix: str,
    domain_prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> None:
    """Populate menu_options for a MENU flow result."""
    step_id = result["step_id"]
    formatted["step_id"] = step_id
    step_prefix = f"{domain_prefix}.step.{step_id}"
    trans_step_prefix = f"{base_prefix}.step.{step_id}"

    _resolve_step_title_and_description(
        formatted,
        trans,
        title_trans,
        domain,
        step_prefix,
        trans_step_prefix,
        placeholders,
    )

    raw_menu_options = result.get("menu_options", [])
    menu_options_out: JsonObjectType = {}
    option_keys: Iterable[str] = (
        raw_menu_options.keys()
        if isinstance(raw_menu_options, Mapping)
        else raw_menu_options
        if isinstance(raw_menu_options, Iterable)
        else ()
    )

    for opt in option_keys:
        label = (
            trans.get(f"{trans_step_prefix}.menu_options.{opt}")
            or trans.get(f"{step_prefix}.menu_options.{opt}")
            or (raw_menu_options[opt] if isinstance(raw_menu_options, Mapping) else opt)
        )
        opt_desc = trans.get(
            f"{trans_step_prefix}.menu_option_descriptions.{opt}"
        ) or trans.get(f"{step_prefix}.menu_option_descriptions.{opt}")
        label_str = _interpolate_placeholders(label, placeholders) or opt
        if opt_desc_str := _interpolate_placeholders(opt_desc, placeholders):
            menu_options_out[opt] = {
                "label": label_str,
                "description": opt_desc_str,
            }
        else:
            menu_options_out[opt] = label_str
    formatted["menu_options"] = menu_options_out


def _format_terminal_or_progress_step(
    hass: HomeAssistant,
    formatted: JsonObjectType,
    result: data_entry_flow.FlowResult[Any, Any],
    flow_type: data_entry_flow.FlowResultType | str,
    trans: dict[str, str],
    title_trans: dict[str, str],
    domain: str,
    base_prefix: str,
    domain_prefix: str,
    placeholders: Mapping[str, Any] | None,
) -> None:
    """Populate fields for CREATE_ENTRY, ABORT, or SHOW_PROGRESS."""
    if flow_type is data_entry_flow.FlowResultType.CREATE_ENTRY:
        if title := result.get("title"):
            formatted["title"] = title
        desc_key = result.get("description") or "default"
        if desc := _interpolate_placeholders(
            trans.get(f"{base_prefix}.create_entry.{desc_key}")
            or trans.get(f"{domain_prefix}.create_entry.{desc_key}"),
            placeholders,
        ):
            formatted["description"] = desc
        if isinstance(created_entry := result.get("result"), ConfigEntry):
            short_ids = _format_short_entry_ids(
                hass.config_entries.async_entries(
                    created_entry.domain, include_ignore=True, include_disabled=True
                )
            )
            formatted["entry_id"] = short_ids.get(
                created_entry.entry_id,
                f"{created_entry.domain}:{created_entry.entry_id[-_MIN_SHORT_ID_LEN:]}",
            )

    elif flow_type is data_entry_flow.FlowResultType.ABORT:
        reason = result["reason"]
        formatted["reason"] = reason
        abort_msg = (
            trans.get(f"{base_prefix}.abort.{reason}")
            or trans.get(f"{domain_prefix}.abort.{reason}")
            or trans.get(f"component.homeassistant.config.abort.{reason}")
        )
        if abort_text := _interpolate_placeholders(abort_msg, placeholders):
            formatted["description"] = abort_text

    elif flow_type is data_entry_flow.FlowResultType.SHOW_PROGRESS:
        step_id = result["step_id"]
        progress_action = result["progress_action"]
        formatted["step_id"] = step_id
        formatted["progress_action"] = progress_action
        step_prefix = f"{domain_prefix}.step.{step_id}"
        trans_step_prefix = f"{base_prefix}.step.{step_id}"
        if title := _interpolate_placeholders(
            trans.get(f"{trans_step_prefix}.title")
            or trans.get(f"{step_prefix}.title")
            or title_trans.get(f"component.{domain}.title"),
            placeholders,
        ):
            formatted["title"] = title
        if description := _interpolate_placeholders(
            trans.get(f"{base_prefix}.progress.{progress_action}")
            or trans.get(f"{domain_prefix}.progress.{progress_action}"),
            placeholders,
        ):
            formatted["description"] = description

    if isinstance(next_flow := result.get("next_flow"), tuple) and len(next_flow) == 2:
        formatted["next_flow"] = {
            "flow_type": str(next_flow[0]),
            "flow_id": str(next_flow[1]),
        }


async def async_format_flow_result(
    hass: HomeAssistant,
    result: data_entry_flow.FlowResult[Any, Any],
    domain: str,
    language: str | None,
) -> JsonObjectType:
    """Format a DataEntryFlow result with resolved translations and field metadata."""
    trans_domain: str = result.get("translation_domain") or domain
    (
        trans,
        base_prefix,
        domain_prefix,
        lang,
    ) = await _async_load_flow_translations(hass, domain, trans_domain, language)
    title_trans = await translation.async_get_translations(
        hass, lang, "title", {domain}
    )

    placeholders: Mapping[str, Any] | None = result.get("description_placeholders")
    flow_type = result["type"]
    formatted: JsonObjectType = {
        "flow_id": result["flow_id"],
        "type": str(
            flow_type.value
            if isinstance(flow_type, data_entry_flow.FlowResultType)
            else flow_type
        ),
    }

    if flow_type is data_entry_flow.FlowResultType.FORM:
        selector_trans = await translation.async_get_translations(
            hass, lang, "selector", {domain, trans_domain, "homeassistant"}
        )
        _format_form_step(
            formatted,
            result,
            trans,
            title_trans,
            selector_trans,
            domain,
            trans_domain,
            base_prefix,
            domain_prefix,
            placeholders,
        )
    elif flow_type is data_entry_flow.FlowResultType.MENU:
        _format_menu_step(
            formatted,
            result,
            trans,
            title_trans,
            domain,
            base_prefix,
            domain_prefix,
            placeholders,
        )
    else:
        _format_terminal_or_progress_step(
            hass,
            formatted,
            result,
            flow_type,
            trans,
            title_trans,
            domain,
            base_prefix,
            domain_prefix,
            placeholders,
        )

    return formatted


async def async_format_schema_errors(
    hass: HomeAssistant,
    flow_id: str,
    cur_step: data_entry_flow.FlowResult[Any, Any],
    schema_errors: dict[str, Any],
    domain: str,
    language: str | None,
) -> JsonObjectType:
    """Format schema validation errors for a flow step without re-serializing fields."""
    trans_domain: str = cur_step.get("translation_domain") or domain
    (
        trans,
        base_prefix,
        domain_prefix,
        _,
    ) = await _async_load_flow_translations(hass, domain, trans_domain, language)
    flow_type = cur_step["type"]
    return {
        "flow_id": flow_id,
        "type": str(
            flow_type.value
            if isinstance(flow_type, data_entry_flow.FlowResultType)
            else flow_type
        ),
        "step_id": str(cur_step.get("step_id", "user")),
        "errors": _translate_errors(
            schema_errors,
            trans,
            base_prefix,
            domain_prefix,
            cur_step.get("description_placeholders"),
        ),
    }


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


def _abort_uninitialized_flows(
    flow_mgr: data_entry_flow.FlowManager[Any, Any, Any], domain: str
) -> None:
    """Abort any uninitialized user flows left behind when async_init raises."""
    for flw in flow_mgr.async_progress_by_handler(domain, include_uninitialized=True):
        if (
            "step_id" not in flw
            and flw["context"].get("source") == config_entries.SOURCE_USER
        ):
            with suppress(data_entry_flow.UnknownFlow):
                flow_mgr.async_abort(flw["flow_id"])


async def _async_finalize_flow_step(
    hass: HomeAssistant,
    flow_mgr: data_entry_flow.FlowManager[Any, Any, Any],
    result: data_entry_flow.FlowResult[Any, Any],
    domain: str,
    language: str | None,
) -> ToolResult:
    """Handle external/OAuth steps or format the flow result."""
    flow_type = result["type"]
    if (
        flow_type is data_entry_flow.FlowResultType.EXTERNAL_STEP
        or result.get("step_id") == "pick_implementation"
    ):
        with suppress(data_entry_flow.UnknownFlow):
            flow_mgr.async_abort(result["flow_id"])
        return _build_external_step_error(domain)
    if (
        flow_type is data_entry_flow.FlowResultType.ABORT
        and result.get("reason") == "missing_credentials"
    ):
        return _build_external_step_error(domain)

    formatted = await async_format_flow_result(hass, result, domain, language)
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
        except RuntimeError as err:
            if str(err) not in _OAUTH_RUNTIME_ERRORS:
                raise
            _abort_uninitialized_flows(hass.config_entries.flow, domain)
            return _build_external_step_error(domain)
        except data_entry_flow.UnknownStep as err:
            return _error_result(str(err))
        except DependencyError as err:
            return _error_result(
                f"Failed dependencies: {', '.join(err.failed_dependencies)}"
            )
        except HomeAssistantError as err:
            _abort_uninitialized_flows(hass.config_entries.flow, domain)
            return _error_result(str(err))

        return await _async_finalize_flow_step(
            hass,
            hass.config_entries.flow,
            result,
            domain,
            llm_context.language,
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
                description="The flow_id of the in-progress flow.",
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
        flow_id: str = args["flow_id"]
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

        flow_mgr = hass.config_entries.flow
        if (
            flow_handler := flow_mgr._progress.get(flow_id)  # noqa: SLF001
        ) is None or (cur_step := flow_handler.cur_step) is None:
            return _error_result(f"Flow '{flow_id}' not found.")

        domain = str(flow_handler.handler)

        if abort:
            flow_mgr.async_abort(flow_id)
            return ToolResult(
                data={
                    "result": {
                        "flow_id": flow_id,
                        "type": "abort",
                        "reason": "aborted",
                    }
                }
            )

        cur_type = cur_step.get("type")
        if (
            cur_type is data_entry_flow.FlowResultType.EXTERNAL_STEP
            or cur_step.get("step_id") == "pick_implementation"
        ):
            return await _async_finalize_flow_step(
                hass,
                flow_mgr,
                cur_step,
                domain,
                llm_context.language,
            )
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
            return await _async_finalize_flow_step(
                hass,
                flow_mgr,
                cur_step,
                domain,
                llm_context.language,
            )

        flow_input: dict[str, Any] | None = (
            {"next_step_id": next_step_id} if next_step_id is not None else user_input
        )

        try:
            result = await flow_mgr.async_configure(flow_id, flow_input)
        except data_entry_flow.InvalidData as err:
            formatted = await async_format_schema_errors(
                hass,
                flow_id,
                cur_step,
                err.schema_errors,
                domain,
                llm_context.language,
            )
            return ToolResult(data={"result": formatted}, error=True)
        except RuntimeError as err:
            if str(err) not in _OAUTH_RUNTIME_ERRORS:
                raise
            with suppress(data_entry_flow.UnknownFlow):
                flow_mgr.async_abort(flow_id)
            return _build_external_step_error(domain)
        except data_entry_flow.UnknownFlow:
            return _error_result(f"Flow '{flow_id}' not found.")
        except HomeAssistantError as err:
            return _error_result(str(err))

        return await _async_finalize_flow_step(
            hass,
            flow_mgr,
            result,
            domain,
            llm_context.language,
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
