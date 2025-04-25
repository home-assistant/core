"""Tests for the Kem update coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiokem import AuthenticationError, CommunicationError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.kem.const import SCAN_INTERVAL_MINUTES
from homeassistant.components.kem.coordinator import MAX_RETRIES
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def test_coordinator_retries(
    hass: HomeAssistant,
    platform_sensor,
    mock_kem_get_generator_data: AsyncMock,
    mock_kem_authenticate: AsyncMock,
    generator: dict[str, any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the KEM sensors."""

    # Test a retryable error
    mock_kem_get_generator_data.reset_mock()
    mock_kem_get_generator_data.side_effect = CommunicationError("Comms error")
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(SCAN_INTERVAL_MINUTES)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem_get_generator_data.call_count == MAX_RETRIES

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test a non-retryable error
    mock_kem_get_generator_data.reset_mock()
    mock_kem_get_generator_data.side_effect = Exception("An exception")
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(SCAN_INTERVAL_MINUTES)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem_get_generator_data.call_count == 1

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test an authentication error
    # This should result in reauthenticating.
    mock_kem_authenticate.reset_mock()
    mock_kem_get_generator_data.reset_mock()
    mock_kem_get_generator_data.side_effect = [
        AuthenticationError("An exception"),
        generator,
    ]
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(SCAN_INTERVAL_MINUTES)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem_get_generator_data.call_count == 2
    assert mock_kem_authenticate.call_count == 1

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == "Standby"

    # Test a persistent authentication error
    # This should result in failure with no retries.
    mock_kem_authenticate.reset_mock()
    mock_kem_authenticate.side_effect = AuthenticationError("Unauthorized")
    mock_kem_get_generator_data.reset_mock()
    mock_kem_get_generator_data.side_effect = [
        AuthenticationError("An exception"),
        generator,
    ]
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(SCAN_INTERVAL_MINUTES)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem_get_generator_data.call_count == 1
    assert mock_kem_authenticate.call_count == 1

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE
