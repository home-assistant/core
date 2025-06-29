"""Test for Fast.com component Init."""

from __future__ import annotations

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

    from homeassistant.components.fastdotcom.coordinator import (
        FastdotcomDataUpdateCoordinator,
    )

    coordinator = FastdotcomDataUpdateCoordinator(hass, config_entry)
    # Manually set required attributes to avoid errors
    coordinator.config_entry = config_entry
    coordinator.data = None
    coordinator.last_update_success = True
    coordinator._unsub_refresh = None

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert coordinator is not None, "Coordinator was not created during setup"
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_delayed_speedtest_during_startup(
    hass: HomeAssistant,
) -> None:
    """Test delayed speedtest during startup and verify sensor entity IDs and states."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    # Set Home Assistant to starting state so that the coordinator does not refresh immediately.
    hass.set_state(CoreState.starting)

    from homeassistant.components.fastdotcom.coordinator import (
        FastdotcomDataUpdateCoordinator,
    )

    coordinator = FastdotcomDataUpdateCoordinator(hass, config_entry)
    # Manually set required attributes to avoid errors
    coordinator.config_entry = config_entry
    coordinator.last_update_success = True
    coordinator._unsub_refresh = None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that sensor entities are created with the expected entity IDs.
    # Expected sensor names are based on: "{DEFAULT_NAME} {description.name}"
    # For DEFAULT_NAME "Fast.com" and description "download speed", the entity_id is auto-generated as:
    # "sensor.fast_com_download_speed" (slugified)
    download_sensor = hass.states.get("sensor.fast_com_download_speed")
    assert download_sensor is not None, "Download sensor was not created"
    assert download_sensor.state == "unknown"

    upload_sensor = hass.states.get("sensor.fast_com_upload_speed")
    assert upload_sensor is not None, "Upload sensor was not created"
    assert upload_sensor.state == "unknown"

    unloaded_ping_sensor = hass.states.get("sensor.fast_com_unloaded_ping")
    assert unloaded_ping_sensor is not None, "Unloaded ping sensor was not created"
    assert unloaded_ping_sensor.state == "unknown"

    loaded_ping_sensor = hass.states.get("sensor.fast_com_loaded_ping")
    assert loaded_ping_sensor is not None, "Loaded ping sensor was not created"
    assert loaded_ping_sensor.state == "unknown"

    # Now simulate real data after Home Assistant has started.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    # Trigger a manual refresh.
    await coordinator.async_refresh()
    coordinator.async_update_listeners()  # Explicitly trigger listeners.
    await hass.async_block_till_done()

    # Verify that sensor states now reflect the real data.
    download_sensor = hass.states.get("sensor.fast_com_download_speed")
    assert download_sensor is not None, "Download sensor missing after refresh"

    upload_sensor = hass.states.get("sensor.fast_com_upload_speed")
    assert upload_sensor is not None, "Upload sensor missing after refresh"

    unloaded_ping_sensor = hass.states.get("sensor.fast_com_unloaded_ping")
    assert unloaded_ping_sensor is not None, (
        "Unloaded ping sensor missing after refresh"
    )

    loaded_ping_sensor = hass.states.get("sensor.fast_com_loaded_ping")
    assert loaded_ping_sensor is not None, "Loaded ping sensor missing after refresh"
