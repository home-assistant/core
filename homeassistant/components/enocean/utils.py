"""Hold utility functions."""
from __future__ import annotations

import logging

from enocean.communicators import Communicator

import homeassistant.components.enocean as ec
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


def get_communicator_reference(hass: HomeAssistant) -> object | Communicator:
    """Get a reference to the communicator (dongle/pihat)."""
    enocean_data = hass.data.get(ec.DATA_ENOCEAN, {})
    dongle: ec.EnOceanDongle = enocean_data[ec.ENOCEAN_DONGLE]
    if not dongle:
        LOGGER.error("No EnOcean Dongle configured or available. No teach-in possible.")
        return None
    communicator: Communicator = dongle.communicator
    return communicator


def int_to_list(int_value):
    """Convert integer to list of values."""
    result = []
    while int_value > 0:
        result.append(int_value % 256)
        int_value = int_value // 256
    result.reverse()
    return result


def hex_to_list(hex_value):
    """Convert hexadecimal value to a list of int values."""
    # it FFD97F81 has to be [FF, D9, 7F, 81] => [255, 217, 127, 129]
    result = []
    if hex_value is None:
        return result

    while hex_value > 0:
        result.append(hex_value % 0x100)
        hex_value = hex_value // 256
    result.reverse()
    return result
