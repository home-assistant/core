"""The doorbird integration models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .device import ConfiguredDoorBird

type DoorBirdConfigEntry = ConfigEntry[DoorBirdData]


@dataclass
class DoorBirdData:
    """Data for the doorbird integration."""

    door_station: ConfiguredDoorBird
    door_station_info: dict[str, Any]

    #
    # This integration uses a different event for
    # each entity id. It would be a major breaking
    # change to change this to a single event at this
    # point.
    #
    # Do not copy this pattern in the future
    # for any new integrations.
    #
    event_entity_ids: dict[str, str]
