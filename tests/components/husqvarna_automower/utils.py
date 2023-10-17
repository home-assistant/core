"""Tests helper for Husqvarna Automower tests."""

from aioautomower.model import MowerList

from .const import AUTOMOWER_SM_SESSION_DATA


def make_mower_data() -> MowerList:
    """Generate a mower object."""
    mower = MowerList(**AUTOMOWER_SM_SESSION_DATA)
    return mower
