"""Tests for the FlashForge 3D Printer sensors."""
from unittest.mock import patch

from homeassistant.components.flashforge.const import DOMAIN
from homeassistant.components.flashforge.data_update_coordinator import (
    FlashForgeDataUpdateCoordinator,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import change_printer_values, init_integration, prepare_mocked_connection


async def test_sensors(hass: HomeAssistant):
    """Test Flashforge sensors."""
    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)
        change_printer_values(mock_network.return_value)

        await init_integration(hass)

    registry = entity_registry.async_get(hass)

    # states = hass.states.async_entity_ids()
    # entries = entity_registry.async_entries_for_device(
    #     registry, device_id="SNADVA1234567"
    # )

    # Temp Sensors.
    state = hass.states.get("sensor.flashforge_t0_now_temp")
    assert state is not None
    assert state.state == "198"
    assert state.name == "FlashForge t0 now temp"
    entry = registry.async_get("sensor.flashforge_t0_now_temp")
    assert entry.unique_id == "t0 now temp-SNADVA1234567"

    state = hass.states.get("sensor.flashforge_t0_target_temp")
    assert state is not None
    assert state.state == "210"
    assert state.name == "FlashForge t0 target temp"
    entry = registry.async_get("sensor.flashforge_t0_target_temp")
    assert entry.unique_id == "t0 target temp-SNADVA1234567"

    state = hass.states.get("sensor.flashforge_b_now_temp")
    assert state is not None
    assert state.state == "48"
    assert state.name == "FlashForge b now temp"
    entry = registry.async_get("sensor.flashforge_b_now_temp")
    assert entry.unique_id == "b now temp-SNADVA1234567"

    state = hass.states.get("sensor.flashforge_b_target_temp")
    assert state is not None
    assert state.state == "64"
    assert state.name == "FlashForge b target temp"
    entry = registry.async_get("sensor.flashforge_b_target_temp")
    assert entry.unique_id == "b target temp-SNADVA1234567"

    # Job status sensors.
    state = hass.states.get("sensor.flashforge_current_state")
    assert state is not None
    assert state.state == "BUILDING_FROM_SD"
    assert state.name == "FlashForge Current State"
    entry = registry.async_get("sensor.flashforge_current_state")
    assert entry.unique_id == "Current State-SNADVA1234567"

    state = hass.states.get("sensor.flashforge_job_percentage")
    assert state is not None
    assert state.state == "11"
    assert state.name == "FlashForge Job Percentage"
    entry = registry.async_get("sensor.flashforge_job_percentage")
    assert entry.unique_id == "Job Percentage-SNADVA1234567"


async def test_unload_integration_and_sensors(hass: HomeAssistant):
    """Test Flashforge sensors."""
    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)

        entry = await init_integration(hass)

    # Sensor become unavailable when integration unloads.
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.flashforge_t0_now_temp")
    assert state.state == STATE_UNAVAILABLE

    # Sensor become None when integration is deleted.
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.flashforge_t0_now_temp")
    assert state is None


async def test_sensor_update_error(hass: HomeAssistant):
    """Test Flashforge sensors update error."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        printer_network = mock_network.return_value
        prepare_mocked_connection(printer_network)

        entry = await init_integration(hass)

        state1 = hass.states.get("sensor.flashforge_t0_now_temp")
        assert state1.state == "22"

        # Change printer respond.
        change_printer_values(printer_network)
        printer_network.sendStatusRequest.side_effect = ConnectionError("conn_error")

        # Request sensor update.
        coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][
            entry.entry_id
        ]["coordinator"]
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

        state2 = hass.states.get("sensor.flashforge_t0_now_temp")
        assert state2.state == STATE_UNAVAILABLE


async def test_sensor_update_error2(hass: HomeAssistant):
    """Test Flashforge sensors update TimeoutError."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        printer_network = mock_network.return_value
        prepare_mocked_connection(printer_network)

        entry = await init_integration(hass)

        # Change printer respond.
        change_printer_values(printer_network)
        printer_network.sendStatusRequest.side_effect = TimeoutError("timeout")

        # Request sensor update.
        coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][
            entry.entry_id
        ]["coordinator"]
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

        state3 = hass.states.get("sensor.flashforge_t0_now_temp")
        assert state3.state == STATE_UNAVAILABLE
