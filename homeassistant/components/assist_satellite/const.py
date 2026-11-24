"""Constants for assist satellite."""

import asyncio
from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import AssistSatelliteEntity

DOMAIN: Final = "assist_satellite"

DATA_COMPONENT: HassKey[EntityComponent[AssistSatelliteEntity]] = HassKey(DOMAIN)
CONNECTION_TEST_DATA: HassKey[dict[str, asyncio.Event]] = HassKey(
    f"{DOMAIN}_connection_tests"
)

PREANNOUNCE_FILENAME = "preannounce.mp3"
PREANNOUNCE_URL = f"/api/assist_satellite/static/{PREANNOUNCE_FILENAME}"


class AssistSatelliteEntityFeature(IntFlag):
    """Supported features of Assist satellite entity."""

    ANNOUNCE = 1
    """Device supports remotely triggered announcements."""

    START_CONVERSATION = 2
    """Device supports starting conversations."""


class AssistSatelliteService(StrEnum):
    """Store keys for assist satellite services."""

    ANNOUNCE = "announce"
    ASK_QUESTION = "ask_question"
    START_CONVERSATION = "start_conversation"


class AssistSatelliteServiceArgument(StrEnum):
    """Store keys for assist satellite service arguments."""

    ANSWERS = "answers"
    ENTITY_ID = "entity_id"
    EXTRA_SYSTEM_PROMPT = "extra_system_prompt"
    MEDIA_ID = "media_id"
    MESSAGE = "message"
    PREANNOUNCE = "preannounce"
    PREANNOUNCE_MEDIA_ID = "preannounce_media_id"
    QUESTION = "question"
    QUESTION_MEDIA_ID = "question_media_id"
    START_MEDIA_ID = "start_media_id"
    START_MESSAGE = "start_message"
