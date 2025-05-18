"""Constants for the AI Task integration."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import AITaskEntity

DOMAIN = "ai_task"
DATA_COMPONENT: HassKey[EntityComponent[AITaskEntity]] = HassKey(DOMAIN)

DEFAULT_SYSTEM_PROMPT = (
    "You are a Home Assistant expert and help users with their tasks."
)


class GenTextTaskType(StrEnum):
    """Generate text task types.

    A task type describes the intent of the request in order to
    match the right model for balance of cost and quality.
    """

    GENERATE = "generate"
    """Generate content, which may target a higher quality result."""

    SUMMARY = "summary"
    """Summarize existing content, which be able to use a more cost effective model."""
