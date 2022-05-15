"""Test Scrape component setup process."""
from __future__ import annotations

from homeassistant.components.command_line.const import CONF_COMMAND_TIMEOUT
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant

from . import setup_test_entity


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    await setup_test_entity(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo 1",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )

    state = hass.states.get("sensor.test")
    assert state


async def test_remove_entry(hass: HomeAssistant) -> None:
    """Test remove entry."""
    entry = await setup_test_entity(
        hass,
        {
            CONF_PLATFORM: "sensor",
            CONF_NAME: "Test",
            "command": "echo 1",
            CONF_COMMAND_TIMEOUT: 15,
        },
    )

    state = hass.states.get("sensor.test")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert not state
