"""Constants for the AI Task integration."""

from enum import IntFlag, StrEnum
import logging
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.components.media_source import local_source
    from homeassistant.helpers.entity_component import EntityComponent

    from . import AITaskPreferences
    from .entity import AITaskEntity

DOMAIN: Final = "ai_task"
LOGGER: Final = logging.getLogger(__package__)
DATA_COMPONENT: HassKey[EntityComponent[AITaskEntity]] = HassKey(DOMAIN)
DATA_PREFERENCES: HassKey[AITaskPreferences] = HassKey(f"{DOMAIN}_preferences")
DATA_MEDIA_SOURCE: HassKey[local_source.LocalSource] = HassKey(f"{DOMAIN}_media_source")

IMAGE_DIR: Final = "image"
IMAGE_EXPIRY_TIME = 60 * 60  # 1 hour

SERVICE_CLEAR_IMAGES = "clear_images"
SERVICE_EVALUATE = "evaluate"
SERVICE_GENERATE_DATA = "generate_data"
SERVICE_GENERATE_IMAGE = "generate_image"

ATTR_DAYS: Final = "days"
ATTR_QUESTIONS: Final = "questions"
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
    """Support attachments for all supported tasks."""

    GENERATE_IMAGE = 4
    """Generate images based on instructions."""

    EVALUATE = 8
    """Evaluate typed questions."""


class AITaskService(StrEnum):
    """Store keys for ai task services."""

    CLEAR_IMAGES = "clear_images"
    EVALUATE = "evaluate"
    GENERATE_DATA = "generate_data"
    GENERATE_IMAGE = "generate_image"


class AITaskServiceArgument(StrEnum):
    """Store keys for ai task service arguments."""

    ATTACHMENTS = "attachments"
    DAYS = "days"
    ENTITY_ID = "entity_id"
    INSTRUCTIONS = "instructions"
    QUESTIONS = "questions"
    STATE = "state"
    STRUCTURE = "structure"
    TASK_NAME = "task_name"
