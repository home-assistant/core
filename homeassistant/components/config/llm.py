"""LLM tools for the config integration."""

from typing import override

import probatio

from homeassistant import config_entries
from homeassistant.components.llm import LLMTools
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
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


def _format_short_entry_id(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Return a short domain-scoped entry_id (e.g. 'hue:8k2m').

    Full 26-character ULIDs consume many tokens and are prone to LLM transcription
    errors across tool calls. In a ULID, the first 10 characters are a millisecond
    timestamp (which can collide when entries are created together) and the last 16
    characters are random. Prefixing the trailing random suffix with '<domain>:'
    scopes lookup to a single domain (where ':' cannot appear in a domain name),
    and the suffix length dynamically expands beyond 4 characters if another entry
    in the same domain shares that suffix.
    """
    full_id = entry.entry_id.lower()
    others = [
        other.entry_id.lower()
        for other in hass.config_entries.async_entries(
            entry.domain, include_ignore=True, include_disabled=True
        )
        if other.entry_id != entry.entry_id
    ]
    length = min(_MIN_SHORT_ID_LEN, len(full_id))
    while length < len(full_id) and any(
        other.endswith(full_id[-length:]) for other in others
    ):
        length += 1
    return f"{entry.domain}:{full_id[-length:]}"


def _resolve_short_entry_id(
    hass: HomeAssistant, entry_id: str
) -> tuple[ConfigEntry | None, str | None]:
    """Resolve a ConfigEntry by short '<domain>:<suffix>' ID or full entry_id.

    Checks for an exact full entry_id match first, then resolves '<domain>:<suffix>'
    against entries of that domain by matching the trailing suffix.
    """
    if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
        return entry, None

    domain, sep, suffix = entry_id.partition(":")
    if not sep or not domain or not suffix:
        return None, f"Config entry '{entry_id}' not found."

    suffix_lower = suffix.lower()
    matches = [
        candidate
        for candidate in hass.config_entries.async_entries(
            domain.lower(), include_ignore=True, include_disabled=True
        )
        if candidate.entry_id.lower().endswith(suffix_lower)
    ]
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f"Config entry '{entry_id}' not found."

    options = ", ".join(
        f"{_format_short_entry_id(hass, candidate)} ({candidate.title!r})"
        for candidate in matches
    )
    return (
        None,
        f"Config entry '{entry_id}' is ambiguous; matches: {options}.",
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


def _format_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> JsonObjectType:
    """Format a ConfigEntry into a compact dictionary for LLM consumption."""
    result: JsonObjectType = {
        "entry_id": _format_short_entry_id(hass, entry),
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

        if status_filter is not None:
            allowed_states = _STATUS_STATES[status_filter]
            entries = [entry for entry in entries if entry.state in allowed_states]

        return ToolResult(
            data={
                "result": list[JsonValueType](
                    _format_config_entry(hass, entry) for entry in entries
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

        entry, error = _resolve_short_entry_id(hass, entry_id)
        if entry is None:
            return ToolResult(
                data={"error": error},
                error=True,
            )
        short_id = _format_short_entry_id(hass, entry)
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
        except config_entries.OperationNotAllowed as err:
            return ToolResult(
                data={"error": f"Config entry cannot be reloaded: {err}"},
                error=True,
            )

        result: JsonObjectType = {
            "entry_id": short_id,
            "state": entry.state.value,
            "require_restart": not entry.state.recoverable,
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
