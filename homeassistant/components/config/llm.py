"""LLM tools for the config integration."""

from collections import defaultdict
from collections.abc import Iterable
from typing import override

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


def _format_short_entry_ids(entries: Iterable[ConfigEntry]) -> dict[str, str]:
    """Return a mapping of full entry_id to short '<domain>:<suffix>' ID.

    Short IDs reduce token usage and LLM transcription errors across tool calls.
    The trailing suffix starts at 4 characters and expands if another entry in the
    same domain shares that suffix.
    """
    groups: defaultdict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for entry in entries:
        full_lower = entry.entry_id.lower()
        groups[(entry.domain, full_lower[-_MIN_SHORT_ID_LEN:])].append(
            (entry.entry_id, full_lower)
        )

    result: dict[str, str] = {}
    for (domain, _), group in groups.items():
        for entry_id, full_lower in group:
            length = min(_MIN_SHORT_ID_LEN, len(full_lower))
            while length < len(full_lower) and any(
                other_lower.endswith(full_lower[-length:])
                for other_id, other_lower in group
                if other_id != entry_id
            ):
                length += 1
            result[entry_id] = f"{domain}:{full_lower[-length:]}"
    return result


def _resolve_short_entry_id(
    hass: HomeAssistant, entry_id: str
) -> tuple[ConfigEntry, str]:
    """Resolve a ConfigEntry and its short ID by '<domain>:<suffix>' or full entry_id.

    Checks for an exact full entry_id match first, then resolves '<domain>:<suffix>'
    against entries of that domain by matching the trailing suffix.
    """
    if (
        entry := hass.config_entries.async_get_entry(entry_id)
        or hass.config_entries.async_get_entry(entry_id.upper())
    ) is not None:
        short_ids = _format_short_entry_ids(
            hass.config_entries.async_entries(entry.domain)
        )
        return entry, short_ids[entry.entry_id]

    domain, sep, suffix = entry_id.partition(":")
    domain = domain.strip().lower()
    suffix_lower = suffix.strip().lower()
    if not sep or not domain or len(suffix_lower) < _MIN_SHORT_ID_LEN:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")

    domain_entries = hass.config_entries.async_entries(domain)
    matches = [
        candidate
        for candidate in domain_entries
        if candidate.entry_id.lower().endswith(suffix_lower)
    ]
    if not matches:
        raise HomeAssistantError(f"Config entry '{entry_id}' not found.")

    short_ids = _format_short_entry_ids(domain_entries)
    if len(matches) == 1:
        match = matches[0]
        return match, short_ids[match.entry_id]

    options = ", ".join(
        f"{short_ids[candidate.entry_id]} ({candidate.title!r})"
        for candidate in matches
    )
    raise HomeAssistantError(
        f"Config entry '{entry_id}' is ambiguous; matches: {options}."
    )


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
                    "The entry_id of the config entry to reload (e.g. 'hue:8k2m')."
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
            entry, short_id = _resolve_short_entry_id(hass, entry_id)
        except HomeAssistantError as err:
            return ToolResult(data={"error": str(err)}, error=True)

        if entry.disabled_by is not None:
            return ToolResult(
                data={
                    "error": (
                        f"Config entry '{short_id}' cannot be reloaded because it is "
                        "disabled."
                    )
                },
                error=True,
            )
        if entry.source == config_entries.SOURCE_IGNORE:
            return ToolResult(
                data={
                    "error": (
                        f"Config entry '{short_id}' cannot be reloaded because it is "
                        "ignored."
                    )
                },
                error=True,
            )

        try:
            await hass.config_entries.async_reload(entry.entry_id)
        except config_entries.OperationNotAllowed:
            return ToolResult(
                data={
                    "error": (
                        f"Config entry '{short_id}' cannot be reloaded in state "
                        f"'{entry.state.value}'."
                    )
                },
                error=True,
            )

        result: JsonObjectType = {
            "entry_id": short_id,
            "state": entry.state.value,
        }
        if (reason := _resolve_entry_reason(entry)) is not None:
            result["reason"] = reason

        return ToolResult(data={"result": result})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the config LLM tools for the Home Assistant API."""
    if api_id != LLM_API_HOME_ASSISTANT:
        return None

    return LLMTools(tools=[GetConfigEntriesTool(), ReloadConfigEntryTool()])
