"""Constants for the AI Task integration."""

from __future__ import annotations

from enum import IntFlag
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import AITaskPreferences
    from .entity import AITaskEntity
    from .task import ImageData

DOMAIN = "ai_task"
DATA_COMPONENT: HassKey[EntityComponent[AITaskEntity]] = HassKey(DOMAIN)
DATA_PREFERENCES: HassKey[AITaskPreferences] = HassKey(f"{DOMAIN}_preferences")
DATA_IMAGES: HassKey[dict[str, ImageData]] = HassKey(f"{DOMAIN}_images")

IMAGE_EXPIRY_TIME = 60 * 60  # 1 hour
MAX_IMAGES = 20

SERVICE_GENERATE_DATA = "generate_data"
SERVICE_GENERATE_IMAGE = "generate_image"

ATTR_INSTRUCTIONS: Final = "instructions"
ATTR_TASK_NAME: Final = "task_name"
ATTR_STRUCTURE: Final = "structure"
ATTR_REQUIRED: Final = "required"
ATTR_ATTACHMENTS: Final = "attachments"

DEFAULT_SYSTEM_PROMPT = (
    "You are a Home Assistant expert and help users with their tasks."
)


class AITaskEntityFeature(IntFlag):
    """Supported features of the AI task entity."""

    GENERATE_DATA = 1
    """Generate data based on instructions."""

    SUPPORT_ATTACHMENTS = 2
    """Support attachments with generate data."""

    GENERATE_IMAGE = 4
    """Generate images based on instructions."""
