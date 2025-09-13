"""Test for Fast.com component Init."""

from __future__ import annotations

from homeassistant.components.fastdotcom.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry cleans up runtime_data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    # Setup the integration
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hasattr(config_entry, "runtime_data")

    # Now unload and verify cleanup
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(config_entry, "runtime_data")


async def test_delayed_speedtest_during_startup(hass: HomeAssistant) -> None:
    """Test delayed speedtest during startup and verify sensor entity IDs and states."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    # Simulate HA starting
    hass.set_state(CoreState.starting)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that entities exist but are "unknown"
    for sensor_id in [
        "sensor.fast_com_download_speed",
        "sensor.fast_com_upload_speed",
        "sensor.fast_com_unloaded_ping",
        "sensor.fast_com_loaded_ping",
    ]:
        state = hass.states.get(sensor_id)
        assert state is not None
        assert state.state == "unknown"

    # Simulate HA finishing startup
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Run refresh manually
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # Ensure sensors are still available after refresh
    for sensor_id in [
        "sensor.fast_com_download_speed",
        "sensor.fast_com_upload_speed",
        "sensor.fast_com_unloaded_ping",
        "sensor.fast_com_loaded_ping",
    ]:
        state = hass.states.get(sensor_id)
        assert state is not None
