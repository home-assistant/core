"""Constants for assist satellite."""

from __future__ import annotations

import asyncio
from enum import IntFlag
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import AssistSatelliteEntity

DOMAIN = "assist_satellite"

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
