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
            "unloaded_ping": 5.0,
            "loaded_ping": 5.0,
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
    """Test delayed speedtest during startup and verify sensor entity IDs and states."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="UNIQUE_TEST_ID",
        title=DEFAULT_NAME,
    )
    config_entry.add_to_hass(hass)

    # Set Home Assistant to starting state so that the coordinator does not refresh immediately.
    hass.set_state(CoreState.starting)

    # Initial coordinator refresh with placeholder (zero) data
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        return_value={
            "download_speed": 0.0,
            "upload_speed": 0.0,
            "unloaded_ping": 0.0,
            "loaded_ping": 0.0,
        },
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)
    assert coordinator is not None, "Coordinator was not created during setup"

    # Verify that sensor entities are created with the expected entity IDs.
    # Expected sensor names are based on: "{DEFAULT_NAME} {description.name}"
    # For DEFAULT_NAME "Fast.com" and description "download speed", the entity_id is auto-generated as:
    # "sensor.fast_com_download_speed" (slugified)
    download_sensor = hass.states.get("sensor.fast_com_download_speed")
    assert download_sensor is not None, "Download sensor was not created"
    # Initially, the placeholder data returns 0.0
    assert download_sensor.state == "0.0"

    upload_sensor = hass.states.get("sensor.fast_com_upload_speed")
    assert upload_sensor is not None, "Upload sensor was not created"
    assert upload_sensor.state == "0.0"

    unloaded_ping_sensor = hass.states.get("sensor.fast_com_unloaded_ping")
    assert unloaded_ping_sensor is not None, "Unloaded ping sensor was not created"
    assert unloaded_ping_sensor.state == "0.0"

    loaded_ping_sensor = hass.states.get("sensor.fast_com_loaded_ping")
    assert loaded_ping_sensor is not None, "Loaded ping sensor was not created"
    assert loaded_ping_sensor.state == "0.0"

    # Now simulate real data after Home Assistant has started.
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com2",
        return_value={
            "download_speed": 1.0,
            "upload_speed": 2.0,
            "unloaded_ping": 3.0,
            "loaded_ping": 4.0,
        },
    ):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        # Trigger a manual refresh.
        await coordinator.async_refresh()
        coordinator.async_update_listeners()  # Explicitly trigger listeners.
        await hass.async_block_till_done()

    # Verify that sensor states now reflect the real data.
    download_sensor = hass.states.get("sensor.fast_com_download_speed")
    assert download_sensor is not None, "Download sensor missing after refresh"
    assert download_sensor.state == "1.0"

    upload_sensor = hass.states.get("sensor.fast_com_upload_speed")
    assert upload_sensor is not None, "Upload sensor missing after refresh"
    assert upload_sensor.state == "2.0"

    unloaded_ping_sensor = hass.states.get("sensor.fast_com_unloaded_ping")
    assert unloaded_ping_sensor is not None, (
        "Unloaded ping sensor missing after refresh"
    )
    assert unloaded_ping_sensor.state == "3.0"

    loaded_ping_sensor = hass.states.get("sensor.fast_com_loaded_ping")
    assert loaded_ping_sensor is not None, "Loaded ping sensor missing after refresh"
    assert loaded_ping_sensor.state == "4.0"
