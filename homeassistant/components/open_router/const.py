"""Constants for the OpenRouter integration."""

from enum import StrEnum
import logging

from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.helpers import llm

DOMAIN = "open_router"
LOGGER = logging.getLogger(__package__)

CONF_RECOMMENDED = "recommended"
CONF_WEB_SEARCH = "web_search"

RECOMMENDED_WEB_SEARCH = False

RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_WEB_SEARCH: RECOMMENDED_WEB_SEARCH,
}


class Parameters(StrEnum):
    """List of supported parameters for a given model.

    Sourced from the str Literal typing at  openrouter.components.parameter.
    """

    TEMPERATURE = "temperature"
    TOP_P = "top_p"
    TOP_K = "top_k"
    MIN_P = "min_p"
    TOP_A = "top_a"
    FREQUENCY_PENALTY = "frequency_penalty"
    PRESENCE_PENALTY = "presence_penalty"
    REPETITION_PENALTY = "repetition_penalty"
    MAX_TOKENS = "max_tokens"
    LOGIT_BIAS = "logit_bias"
    LOGPROBS = "logprobs"
    TOP_LOGPROBS = "top_logprobs"
    SEED = "seed"
    RESPONSE_FORMAT = "response_format"
    STRUCTURED_OUTPUTS = "structured_outputs"
    STOP = "stop"
    TOOLS = "tools"
    TOOL_CHOICE = "tool_choice"
    PARALLEL_TOOL_CALLS = "parallel_tool_calls"
    INCLUDE_REASONING = "include_reasoning"
    REASONING = "reasoning"
    REASONING_EFFORT = "reasoning_effort"
    WEB_SEARCH_OPTIONS = "web_search_options"
    VERBOSITY = "verbosity"
