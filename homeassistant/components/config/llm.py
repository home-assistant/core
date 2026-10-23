"""LLM tools for the config integration."""

from collections.abc import Iterable, Mapping
import re
from typing import Any, override

import probatio

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

_STATUS_FILTERS: dict[str, set[ConfigEntryState]] = {
    "loaded": {ConfigEntryState.LOADED},
    "error": {
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
        ConfigEntryState.FAILED_UNLOAD,
    },
    "not_loaded": {ConfigEntryState.NOT_LOADED},
}
_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")


def _interpolate_placeholders(
    text: str | None, placeholders: Mapping[str, Any] | None
) -> str | None:
    """Replace {placeholder} tokens in a translation string."""
    if not text or not placeholders:
        return text
    return _PLACEHOLDER_RE.sub(
        lambda m: (
            str(placeholders[key])
            if (key := m.group(1)) in placeholders
            else m.group(0)
        ),
        text,
    )


def _resolve_entry_reason(
    entry: ConfigEntry,
    exc_trans: dict[str, str],
    config_trans: dict[str, str],
) -> str | None:
    """Resolve a human-readable error reason for a ConfigEntry."""
    if key := entry.error_reason_translation_key:
        trans_domain = entry.error_reason_translation_domain or entry.domain
        msg = exc_trans.get(f"component.{trans_domain}.exceptions.{key}.message")
        if resolved := _interpolate_placeholders(
            msg, entry.error_reason_translation_placeholders
        ):
            return resolved
        return entry.reason or key
    if (reason := entry.reason) is not None:
        return config_trans.get(
            f"component.{entry.domain}.config.error.{reason}", reason
        )
    return None


async def _async_load_entry_error_translations(
    hass: HomeAssistant,
    entries: Iterable[ConfigEntry],
    language: str | None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Load exception and config error translations for entries with error reasons."""
    exc_domains: set[str] = set()
    config_domains: set[str] = set()
    for entry in entries:
        if entry.error_reason_translation_key:
            exc_domains.add(entry.error_reason_translation_domain or entry.domain)
        elif entry.reason is not None:
            config_domains.add(entry.domain)

    if not exc_domains and not config_domains:
        return {}, {}

    lang = language if language and language != "*" else (hass.config.language or "en")
    exc_trans = (
        await translation.async_get_translations(hass, lang, "exceptions", exc_domains)
        if exc_domains
        else {}
    )
    config_trans = (
        await translation.async_get_translations(hass, lang, "config", config_domains)
        if config_domains
        else {}
    )
    return exc_trans, config_trans


def _format_config_entry(
    entry: ConfigEntry,
    exc_trans: dict[str, str],
    config_trans: dict[str, str],
) -> JsonObjectType:
    """Format a ConfigEntry into a compact dictionary for LLM consumption."""
    result: JsonObjectType = {
        "entry_id": entry.entry_id,
        "domain": entry.domain,
        "title": entry.title,
        "state": entry.state.value,
    }
    if (reason := _resolve_entry_reason(entry, exc_trans, config_trans)) is not None:
        result["reason"] = reason
    return result


class GetConfigEntriesTool(Tool):
    """LLM Tool to list and filter config entries."""

    name = "config__get_config_entries"
    title = "Get config entries"
    description = (
        "Retrieve installed Home Assistant config entries (active integrations and "
        "helpers configured in this instance; excludes ignored and disabled entries). "
        "Use this to inspect which integrations are set up, check their status "
        "('loaded', 'error', 'not_loaded'), and see translated error reasons."
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
            ): probatio.Any(str, [str]),
            probatio.Optional(
                "status",
                description=(
                    "Filter by status: 'loaded' (working normally), 'error' "
                    "(failed setup, retrying, migration error, or failed unload), "
                    "or 'not_loaded'."
                ),
            ): probatio.All(str, probatio.Lower, probatio.In(list(_STATUS_FILTERS))),
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Return matching config entries."""
        args = self.parameters(tool_input.tool_args)
        domain_filter = args.get("domain")
        status_filter: str | None = args.get("status")

        entries = hass.config_entries.async_entries(
            include_ignore=False, include_disabled=False
        )

        if domain_filter is not None:
            if isinstance(domain_filter, str):
                domains = {domain_filter.strip().lower()}
            else:
                domains = {d.strip().lower() for d in domain_filter if d.strip()}
            entries = [entry for entry in entries if entry.domain.lower() in domains]

        if status_filter is not None:
            allowed_states = _STATUS_FILTERS[status_filter]
            entries = [entry for entry in entries if entry.state in allowed_states]

        exc_trans, config_trans = await _async_load_entry_error_translations(
            hass, entries, llm_context.language
        )

        return ToolResult(
            data={
                "result": list[JsonValueType](
                    _format_config_entry(entry, exc_trans, config_trans)
                    for entry in entries
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

    return LLMTools(tools=[GetConfigEntriesTool()])
