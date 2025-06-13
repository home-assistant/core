"""Constants for the AI Task integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import AITaskPreferences
    from .entity import AITaskEntity

DOMAIN = "ai_task"
DATA_COMPONENT: HassKey[EntityComponent[AITaskEntity]] = HassKey(DOMAIN)
DATA_PREFERENCES: HassKey[AITaskPreferences] = HassKey(f"{DOMAIN}_preferences")

DEFAULT_SYSTEM_PROMPT = (
    "You are a Home Assistant expert and help users with their tasks."
)
