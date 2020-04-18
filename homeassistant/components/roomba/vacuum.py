"""Support for Wi-Fi enabled iRobot Roombas."""
import logging

from . import roomba_reported_state
from .braava import BraavaJet
from .const import BLID, DOMAIN, ROOMBA_SESSION
from .roomba import RoombaVacuum, RoombaVacuumCarpetBoost

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data[ROOMBA_SESSION]
    blid = domain_data[BLID]

    # Get the capabilities of our unit
    state = roomba_reported_state(roomba)
    capabilities = state.get("cap", {})
    cap_carpet_boost = capabilities.get("carpetBoost")
    detected_pad = state.get("detectedPad")
    if detected_pad is not None:
        constructor = BraavaJet
    elif cap_carpet_boost == 1:
        constructor = RoombaVacuumCarpetBoost
    else:
        constructor = RoombaVacuum

    roomba_vac = constructor(roomba, blid)
    roomba_vac.register_callback()
    async_add_entities([roomba_vac], True)
