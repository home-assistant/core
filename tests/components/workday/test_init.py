"""Test Workday component setup process."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import TEST_CONFIG_EXAMPLE_1, init_integration


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    await init_integration(hass, TEST_CONFIG_EXAMPLE_1)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state


async def test_remove_entry(hass: HomeAssistant) -> None:
    """Test remove entry."""
    entry = await init_integration(hass, TEST_CONFIG_EXAMPLE_1)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state
