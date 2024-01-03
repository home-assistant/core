"""Tests helper for Husqvarna Automower tests."""

import logging

from aioautomower.model import MowerList

_LOGGER = logging.getLogger(__name__)


def make_mower_list(mower) -> MowerList:
    """Generate a mower object."""
    mowers_list = MowerList(**mower)
    mowers = {}
    for mower in mowers_list.data:
        mowers[mower.id] = mower.attributes
    return mowers
