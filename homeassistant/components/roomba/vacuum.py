"""Support for Wi-Fi enabled iRobot Roombas."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import roomba_reported_state
from .braava import BraavaJet
from .const import BLID, DOMAIN, ROOMBA_SESSION
from .irobot_base import IRobotVacuum
from .roomba import RoombaVacuum, RoombaVacuumCarpetBoost


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]

    # Get the capabilities of our unit
    state = roomba_reported_state(roomba)
    capabilities = state.get("cap", {})
    cap_carpet_boost = capabilities.get("carpetBoost")
    detected_pad = state.get("detectedPad")
    constructor: type[IRobotVacuum]
    if detected_pad is not None:
        constructor = BraavaJet
    elif cap_carpet_boost == 1:
        constructor = RoombaVacuumCarpetBoost
    else:
        constructor = RoombaVacuum

    roomba_vac = constructor(roomba, blid)
    async_add_entities([roomba_vac], True)
