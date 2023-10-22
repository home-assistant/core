"""Tests helper for Husqvarna Automower tests."""

import logging

from aioautomower.model import MowerData, MowerList

from .const import AUTOMOWER_SM_SESSION_DATA, MOWER_ONE_SESSION_DATA

_LOGGER = logging.getLogger(__name__)


def make_single_mower_data() -> MowerData:
    """Generate a mower object."""
    mower = MowerData(**MOWER_ONE_SESSION_DATA)
    return mower


def make_complete_mower_list() -> MowerList:
    """Generate a mower object."""
    mowers_list = MowerList(**AUTOMOWER_SM_SESSION_DATA)
    mowers = {}
    for mower in mowers_list.data:
        mowers[mower.id] = mower.attributes
    return mowers
