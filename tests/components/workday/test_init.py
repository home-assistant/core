"""Test Workday component setup process."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.workday.const import (
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
)
from homeassistant.core import HomeAssistant

from . import TEST_CONFIG_EXAMPLE_1, TEST_CONFIG_WITH_PROVINCE, init_integration


async def test_load_unload_entry(hass: HomeAssistant) -> None:
    """Test load and unload entry."""
    entry = await init_integration(hass, TEST_CONFIG_EXAMPLE_1)

    state = hass.states.get("binary_sensor.workday_sensor")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.workday_sensor")
    assert not state


async def test_update_options(hass: HomeAssistant) -> None:
    """Test we get the form in options."""

    entry = await init_integration(hass, TEST_CONFIG_WITH_PROVINCE)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "province": "NW",
            "excludes": DEFAULT_EXCLUDES,
            "days_offset": DEFAULT_OFFSET,
            "workdays": DEFAULT_WORKDAYS,
            "add_holidays": [],
            "remove_holidays": [],
        },
    )
    await hass.async_block_till_done()

    entry_check = hass.config_entries.async_get_entry("1")
    assert entry_check.state == config_entries.ConfigEntryState.LOADED
    assert entry_check.update_listeners is not None
