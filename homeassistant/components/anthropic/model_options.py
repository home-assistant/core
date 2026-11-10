"""Model-specific options for the Anthropic integration."""

from typing import Any

from anthropic.types import ModelCapabilities, ModelInfo

from .const import (
    CONF_CODE_EXECUTION,
    CONF_EFFORT,
    CONF_MAX_TOKENS,
    CONF_THINKING_BUDGET,
    CONF_THINKING_TYPE,
    CONF_TOOL_SEARCH,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_MAX_USES,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT,
    MIN_THINKING_BUDGET,
    TOOL_SEARCH_UNSUPPORTED_MODELS,
)
from .coordinator import model_alias

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def get_unsupported_tool_options(
    capabilities: ModelCapabilities | None,
) -> set[str]:
    """Return configuration options for explicitly unsupported server tools."""
    unsupported_options: set[str] = set()
    if capabilities is None:
        return unsupported_options

    if not capabilities.server_tools.code_execution.supported:
        unsupported_options.add(CONF_CODE_EXECUTION)
    if not capabilities.server_tools.web_search.supported:
        unsupported_options.update(
            {
                CONF_WEB_SEARCH,
                CONF_WEB_SEARCH_MAX_USES,
                CONF_WEB_SEARCH_USER_LOCATION,
                CONF_WEB_SEARCH_CITY,
                CONF_WEB_SEARCH_REGION,
                CONF_WEB_SEARCH_COUNTRY,
                CONF_WEB_SEARCH_TIMEZONE,
            }
        )
    return unsupported_options


def get_supported_thinking_types(
    capabilities: ModelCapabilities | None,
) -> list[str]:
    """Return the thinking types supported by a model."""
    if capabilities is None:
        return []

    thinking = capabilities.thinking
    return [
        value
        for value in ("disabled", "enabled", "adaptive", "between_tools")
        if (value == "disabled" or thinking.supported)
        and getattr(thinking.types, value).supported
    ]


def get_supported_efforts(capabilities: ModelCapabilities | None) -> list[str]:
    """Return the effort values supported by a model."""
    if capabilities is None or not capabilities.effort.supported:
        return []

    return [
        value
        for value in EFFORT_LEVELS
        if (support := getattr(capabilities.effort, value)) and support.supported
    ]


def is_effort_compatible_with_thinking(
    model_info: ModelInfo, thinking_type: str | None, effort: str
) -> bool:
    """Return whether the effort is compatible with the selected thinking type."""
    # The Models API does not describe restrictions between supported parameters.
    return not (
        effort in ("xhigh", "max")
        and (
            thinking_type == "between_tools"
            or (
                model_alias(model_info.id) in ("claude-haiku-5-5", "claude-opus-5")
                and thinking_type == "disabled"
            )
        )
    )


def reconcile_model_options(options: dict[str, Any], model_info: ModelInfo) -> None:
    """Adjust options and defaults to the selected model's capabilities."""
    capabilities = model_info.capabilities
    for option in get_unsupported_tool_options(capabilities):
        options.pop(option, None)

    if model_info.max_tokens is not None:
        if (
            options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS])
            > model_info.max_tokens
        ):
            options[CONF_MAX_TOKENS] = model_info.max_tokens
        if CONF_THINKING_BUDGET in options:
            options[CONF_THINKING_BUDGET] = min(
                options[CONF_THINKING_BUDGET], model_info.max_tokens - 1
            )

    thinking_types = get_supported_thinking_types(capabilities)
    if thinking_types:
        if options.get(CONF_THINKING_TYPE) not in thinking_types:
            thinking_type = next(
                value
                for value in (
                    DEFAULT[CONF_THINKING_TYPE],
                    "enabled",
                    "disabled",
                    "between_tools",
                )
                if value in thinking_types
            )
            if (
                thinking_type == "enabled"
                and "disabled" in thinking_types
                and options.get(CONF_THINKING_BUDGET, DEFAULT[CONF_THINKING_BUDGET])
                < MIN_THINKING_BUDGET
            ):
                # Legacy manual thinking was disabled by setting its budget to zero.
                thinking_type = "disabled"
            options[CONF_THINKING_TYPE] = thinking_type
    else:
        options.pop(CONF_THINKING_TYPE, None)

    if "enabled" in thinking_types:
        budget = max(
            options.get(CONF_THINKING_BUDGET, DEFAULT[CONF_THINKING_BUDGET]),
            MIN_THINKING_BUDGET,
        )
        if options[CONF_THINKING_TYPE] == "enabled":
            max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS])
            if max_tokens <= MIN_THINKING_BUDGET:
                max_tokens = options[CONF_MAX_TOKENS] = MIN_THINKING_BUDGET + 1
            budget = min(budget, max_tokens - 1)
        options[CONF_THINKING_BUDGET] = budget
    else:
        options.pop(CONF_THINKING_BUDGET, None)

    efforts = [
        value
        for value in get_supported_efforts(capabilities)
        if is_effort_compatible_with_thinking(
            model_info, options.get(CONF_THINKING_TYPE), value
        )
    ]
    if efforts:
        effort_index = EFFORT_LEVELS.index(
            options.get(CONF_EFFORT, DEFAULT[CONF_EFFORT])
        )
        options[CONF_EFFORT] = next(
            (
                value
                for value in reversed(EFFORT_LEVELS[: effort_index + 1])
                if value in efforts
            ),
            efforts[0],
        )
    else:
        options.pop(CONF_EFFORT, None)

    if model_info.id.startswith(tuple(TOOL_SEARCH_UNSUPPORTED_MODELS)):
        options.pop(CONF_TOOL_SEARCH, None)
