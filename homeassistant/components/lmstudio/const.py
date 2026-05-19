"""Constants for the LM Studio integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "lmstudio"

CONF_MODEL: Final = "model"
CONF_PROMPT: Final = "prompt"
CONF_MAX_HISTORY: Final = "max_history"

CONF_TEMPERATURE: Final = "temperature"
CONF_TOP_P: Final = "top_p"
CONF_TOP_K: Final = "top_k"
CONF_MIN_P: Final = "min_p"
CONF_REPEAT_PENALTY: Final = "repeat_penalty"
CONF_MAX_OUTPUT_TOKENS: Final = "max_output_tokens"
CONF_CONTEXT_LENGTH: Final = "context_length"
CONF_REASONING: Final = "reasoning"

DEFAULT_TIMEOUT: Final = 10.0
DEFAULT_MAX_HISTORY: Final = 20

DEFAULT_CONVERSATION_NAME: Final = "LM Studio Conversation"
DEFAULT_AI_TASK_NAME: Final = "LM Studio AI Task"

REASONING_OPTIONS: Final[tuple[str, ...]] = ("off", "low", "medium", "high", "on")
