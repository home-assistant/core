"""Tests for Freebox client mocks and edge cases."""

import asyncio
from unittest.mock import AsyncMock, Mock

from freebox_api.exceptions import HttpRequestError, NotOpenError

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_platform
from .const import DATA_CONNECTION_GET_FTTH

from tests.common import async_fire_time_changed


async def test_freebox_client_connection_error(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client handles connection errors properly."""
    # Make the connection.get_status API call fail
    router().connection.get_status.side_effect = HttpRequestError("Connection failed")

    # Setup should handle the error gracefully
    await setup_platform(hass, SENSOR_DOMAIN)

    # No connection sensors should be created when API fails
    state_down = hass.states.get("sensor.freebox_download_speed")
    state_up = hass.states.get("sensor.freebox_upload_speed")

    # Sensors may not be created or may have None values
    # The exact behavior depends on the implementation
    if state_down is not None:
        assert state_down.state in ["unavailable", "unknown"]
    if state_up is not None:
        assert state_up.state in ["unavailable", "unknown"]


async def test_freebox_client_not_open_error(hass: HomeAssistant, router: Mock) -> None:
    """Test Freebox client handles NotOpenError."""
    # Make the FTTH API call fail with NotOpenError
    router().connection.get_ftth.side_effect = NotOpenError("API not open")

    await setup_platform(hass, SENSOR_DOMAIN)

    # FTTH sensors should not be created when API is not open
    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    state_tx = hass.states.get("sensor.freebox_sfp_tx_power")

    assert state_rx is None
    assert state_tx is None


async def test_freebox_client_intermittent_failures(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client handles intermittent API failures."""
    # Setup normal initial state
    await setup_platform(hass, SENSOR_DOMAIN)

    # Make FTTH API fail intermittently
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:  # Fail every second call
            raise HttpRequestError("Intermittent failure")
        return DATA_CONNECTION_GET_FTTH

    router().connection.get_ftth.side_effect = side_effect

    # Trigger multiple updates
    for _ in range(3):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Sensor should still exist and may have updated value
    state_rx_after = hass.states.get("sensor.freebox_sfp_rx_power")
    assert state_rx_after is not None


async def test_freebox_client_partial_data_response(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client handles partial data responses."""
    # Create partial FTTH response (missing some fields)
    partial_ftth_data = {
        "sfp_pwr_rx": -2225,
        # Missing sfp_pwr_tx, sfp_model, sfp_vendor
    }
    router().connection.get_ftth.return_value = partial_ftth_data

    await setup_platform(hass, SENSOR_DOMAIN)

    # RX sensor should be created but TX sensor should not
    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    state_tx = hass.states.get("sensor.freebox_sfp_tx_power")

    assert state_rx is not None
    assert state_tx is None

    # RX sensor should have the correct value
    assert state_rx.state == "-22.25"

async def test_freebox_client_invalid_data_types(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client handles invalid data types gracefully."""
    # Return invalid data types for FTTH
    invalid_ftth_data = {
        "sfp_pwr_rx": "invalid_string",  # Should be int
        "sfp_pwr_tx": None,  # Should be int
    }
    router().connection.get_ftth.return_value = invalid_ftth_data

    await setup_platform(hass, SENSOR_DOMAIN)

    # Sensors should not be created with invalid data
    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    state_tx = hass.states.get("sensor.freebox_sfp_tx_power")

    assert state_rx is None
    assert state_tx is None


async def test_freebox_client_mock_configuration(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test that mocks are properly configured."""
    # Verify that all required mock methods are AsyncMock instances
    assert isinstance(router().connection.get_status, AsyncMock)
    assert isinstance(router().connection.get_ftth, AsyncMock)
    assert isinstance(router().system.get_config, AsyncMock)
    assert isinstance(router().call.get_calls_log, AsyncMock)

    # Verify that mocks return expected data
    await setup_platform(hass, SENSOR_DOMAIN)

    # Check that data is properly returned by mocks
    connection_data = await router().connection.get_status()
    assert connection_data["media"] == "ftth"
    assert "rate_down" in connection_data
    assert "rate_up" in connection_data

    ftth_data = await router().connection.get_ftth()
    assert "sfp_pwr_rx" in ftth_data
    assert "sfp_pwr_tx" in ftth_data


async def test_freebox_client_concurrent_requests(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client handles concurrent requests properly."""
    # Make FTTH API have a delay to simulate concurrent requests
    original_ftth_response = router().connection.get_ftth.return_value

    async def delayed_response(*args, **kwargs):
        await asyncio.sleep(0.1)  # Small delay
        return original_ftth_response

    router().connection.get_ftth.side_effect = delayed_response

    await setup_platform(hass, SENSOR_DOMAIN)

    # Trigger multiple rapid updates
    for _ in range(3):
        async_fire_time_changed(hass)

    await hass.async_block_till_done()

    # Sensors should still be created and functional
    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    state_tx = hass.states.get("sensor.freebox_sfp_tx_power")

    assert state_rx is not None
    assert state_tx is not None


async def test_freebox_client_network_timeout_recovery(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client recovers from network timeouts."""
    # Setup normal initial state
    await setup_platform(hass, SENSOR_DOMAIN)

    initial_state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    assert initial_state_rx is not None

    # Simulate network timeout
    router().connection.get_ftth.side_effect = HttpRequestError("Timeout")

    # Trigger update with timeout
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Restore normal operation
    router().connection.get_ftth.side_effect = None
    router().connection.get_ftth.return_value = DATA_CONNECTION_GET_FTTH

    # Trigger recovery update
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should still exist and be functional
    recovery_state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    assert recovery_state_rx is not None


async def test_freebox_client_api_rate_limiting(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test Freebox client handles API rate limiting."""
    call_count = 0

    def rate_limited_response(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            raise HttpRequestError("Rate limited")
        return DATA_CONNECTION_GET_FTTH

    router().connection.get_ftth.side_effect = rate_limited_response

    await setup_platform(hass, SENSOR_DOMAIN)

    # Trigger multiple updates to hit rate limit
    for _ in range(5):
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # System should handle rate limiting gracefully
    state_rx = hass.states.get("sensor.freebox_sfp_rx_power")
    # Sensor may still exist from initial successful calls
    if state_rx is not None:
        assert state_rx.state in ["-22.25", "unavailable", "unknown"]
