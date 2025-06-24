"""Constants for the AI Task integration."""

from __future__ import annotations

from enum import IntFlag
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import AITaskPreferences
    from .entity import AITaskEntity

DOMAIN = "ai_task"
DATA_COMPONENT: HassKey[EntityComponent[AITaskEntity]] = HassKey(DOMAIN)
DATA_PREFERENCES: HassKey[AITaskPreferences] = HassKey(f"{DOMAIN}_preferences")

SERVICE_GENERATE_DATA = "generate_data"

ATTR_INSTRUCTIONS: Final = "instructions"
ATTR_TASK_NAME: Final = "task_name"

DEFAULT_SYSTEM_PROMPT = (
    "You are a Home Assistant expert and help users with their tasks."
)


class AITaskEntityFeature(IntFlag):
    """Supported features of the AI task entity."""

    GENERATE_DATA = 1
    """Generate data based on instructions."""
