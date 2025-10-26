"""Tests for Honeywell component."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Honeywell integration in Home Assistant."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def reset_mock(device: MagicMock) -> None:
    """Reset the mocks for test."""
    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()
    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()
