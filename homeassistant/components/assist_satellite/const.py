"""Constants for assist satellite."""

from __future__ import annotations

from enum import IntFlag
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from .entity import AssistSatelliteEntity

DOMAIN = "assist_satellite"

DOMAIN_DATA: HassKey[EntityComponent[AssistSatelliteEntity]] = HassKey(DOMAIN)


class AssistSatelliteEntityFeature(IntFlag):
    """Supported features of Assist satellite entity."""

    ANNOUNCE = 1
    """Device supports remotely triggered announcements."""
