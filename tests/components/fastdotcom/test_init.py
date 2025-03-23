"""Test for Fast.com component Init."""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fastdotcom.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        return_value={
            "download_speed": 5.0,
            "upload_speed": 5.0,
            "ping_loaded": 5.0,
            "ping_unloaded": 5.0,
        },
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)
    assert coordinator is not None, "Coordinator was not created during setup"
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_delayed_speedtest_during_startup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test delayed speedtest during startup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    hass.set_state(CoreState.starting)

    # Initial coordinator refresh with placeholder data
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        return_value={
            "download_speed": 0.0,
            "upload_speed": 0.0,
            "ping_loaded": 0.0,
            "ping_unloaded": 0.0,
        },
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)
    assert coordinator is not None, "Coordinator was not created during setup"

    state = hass.states.get("sensor.download_speed")
    assert state is not None, "Sensor was not created"
    assert state.state == "0.0"

    # Now simulate real data after Home Assistant has started
    # Now simulate real data after Home Assistant has started
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        return_value={
            "download_speed": 5.0,
            "upload_speed": 5.0,
            "ping_loaded": 5.0,
            "ping_unloaded": 5.0,
        },
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        await coordinator.async_refresh()
        coordinator.async_update_listeners()  # Explicitly trigger listeners
        await hass.async_block_till_done()
    state = hass.states.get("sensor.download_speed")
    assert state is not None
    assert state.state == "5.0"
