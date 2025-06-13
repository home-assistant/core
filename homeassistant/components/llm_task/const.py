"""Constants for the LLM Task integration."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import LLMTaskPreferences
    from .entity import LLMTaskEntity

DOMAIN = "llm_task"
DATA_COMPONENT: HassKey[EntityComponent[LLMTaskEntity]] = HassKey(DOMAIN)
DATA_PREFERENCES: HassKey[LLMTaskPreferences] = HassKey("llm_task_preferences")

DEFAULT_SYSTEM_PROMPT = (
    "You are a Home Assistant expert and help users with their tasks."
)


class LLMTaskType(StrEnum):
    """LLM task types.

    A task type describes the intent of the request in order to
    match the right model for balance of cost and quality.
    """

    GENERATE = "generate"
    """Generate content, which may target a higher quality result."""

    SUMMARY = "summary"
    """Summarize existing content, which be able to use a more cost effective model."""
