"""Constants for the OpenAI Conversation integration."""

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.helpers import llm

DOMAIN = "openai_conversation"
LOGGER: logging.Logger = logging.getLogger(__package__)

DEFAULT_CONVERSATION_NAME = "OpenAI Conversation"
DEFAULT_AI_TASK_NAME = "OpenAI AI Task"
DEFAULT_NAME = "OpenAI Conversation"

CONF_CHAT_MODEL = "chat_model"
CONF_CODE_INTERPRETER = "code_interpreter"
CONF_FILENAMES = "filenames"
CONF_MAX_TOKENS = "max_tokens"
CONF_PROMPT = "prompt"
CONF_REASONING_EFFORT = "reasoning_effort"
CONF_RECOMMENDED = "recommended"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_WEB_SEARCH = "web_search"
CONF_WEB_SEARCH_USER_LOCATION = "user_location"
CONF_WEB_SEARCH_CONTEXT_SIZE = "search_context_size"
CONF_WEB_SEARCH_CITY = "city"
CONF_WEB_SEARCH_REGION = "region"
CONF_WEB_SEARCH_COUNTRY = "country"
CONF_WEB_SEARCH_TIMEZONE = "timezone"
RECOMMENDED_CODE_INTERPRETER = False
RECOMMENDED_CHAT_MODEL = "gpt-4o-mini"
RECOMMENDED_MAX_TOKENS = 3000
RECOMMENDED_REASONING_EFFORT = "low"
RECOMMENDED_TEMPERATURE = 1.0
RECOMMENDED_TOP_P = 1.0
RECOMMENDED_WEB_SEARCH = False
RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE = "medium"
RECOMMENDED_WEB_SEARCH_USER_LOCATION = False

UNSUPPORTED_MODELS: list[str] = [
    "o1-mini",
    "o1-mini-2024-09-12",
    "o1-preview",
    "o1-preview-2024-09-12",
    "gpt-4o-realtime-preview",
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-4o-realtime-preview-2024-10-01",
    "gpt-4o-mini-realtime-preview",
    "gpt-4o-mini-realtime-preview-2024-12-17",
]

UNSUPPORTED_WEB_SEARCH_MODELS: list[str] = [
    "gpt-3.5",
    "gpt-4-turbo",
    "gpt-4.1-nano",
    "o1",
    "o3-mini",
]


@dataclass(frozen=True)
class ConversationOptions:
    """Configuration options for conversation."""

    recommended: bool = True
    llm_hass_api: list[str] = field(default_factory=lambda: [llm.LLM_API_ASSIST])
    prompt: str = llm.DEFAULT_INSTRUCTIONS_PROMPT
    chat_model: str = RECOMMENDED_CHAT_MODEL
    max_tokens: int = RECOMMENDED_MAX_TOKENS
    temperature: float = RECOMMENDED_TEMPERATURE
    top_p: float = RECOMMENDED_TOP_P
    reasoning_effort: str = RECOMMENDED_REASONING_EFFORT
    web_search: bool = RECOMMENDED_WEB_SEARCH
    code_interpreter: bool = RECOMMENDED_CODE_INTERPRETER

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            CONF_RECOMMENDED: self.recommended,
            CONF_LLM_HASS_API: self.llm_hass_api,
            CONF_PROMPT: self.prompt,
            CONF_CHAT_MODEL: self.chat_model,
            CONF_MAX_TOKENS: self.max_tokens,
            CONF_TEMPERATURE: self.temperature,
            CONF_TOP_P: self.top_p,
            CONF_REASONING_EFFORT: self.reasoning_effort,
            CONF_WEB_SEARCH: self.web_search,
            CONF_CODE_INTERPRETER: self.code_interpreter,
        }


@dataclass(frozen=True)
class AITaskOptions:
    """Configuration options for AI tasks."""

    recommended: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {CONF_RECOMMENDED: self.recommended}


# Maintain backward compatibility with existing dictionary format
RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}
RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_RECOMMENDED: True,
}
