"""Test Workday component setup process."""

from __future__ import annotations

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from holidays.utils import country_holidays

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import UTC

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


async def test_update_options(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test options update and config entry is reloaded."""
    freezer.move_to(datetime(2023, 4, 12, 12, tzinfo=UTC))  # Monday

    entry = await init_integration(hass, TEST_CONFIG_WITH_PROVINCE)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.update_listeners is not None
    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "on"

    new_options = TEST_CONFIG_WITH_PROVINCE.copy()
    new_options["add_holidays"] = ["2023-04-12"]

    hass.config_entries.async_update_entry(entry, options=new_options)
    await hass.async_block_till_done()

    entry_check = hass.config_entries.async_get_entry("1")
    assert entry_check.state is ConfigEntryState.LOADED
    state = hass.states.get("binary_sensor.workday_sensor")
    assert state.state == "off"


async def test_workday_subdiv_aliases() -> None:
    """Test subdiv aliases in holidays library."""

    country = country_holidays(
        country="FR",
        years=2025,
    )
    subdiv_aliases = country.get_subdivision_aliases()
    assert subdiv_aliases["GES"] == [  # codespell:ignore
        "Alsace",
        "Champagne-Ardenne",
        "Lorraine",
    ]
