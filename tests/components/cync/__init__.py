"""Tests for the Cync integration."""

from __future__ import annotations

from pycync import CyncHome

from homeassistant.core import HomeAssistant

from .const import BEDROOM_ROOM, MAIN_HOME, OFFICE_ROOM

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Sets up the Cync integration to be used in testing."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_mocked_homes() -> list[CyncHome]:
    """Finalizes the setup of the mocked home object."""
    MAIN_HOME.rooms.extend([OFFICE_ROOM, BEDROOM_ROOM])
    return [MAIN_HOME]
