"""Tests for the Kem update coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from aiokem import AioKem, AuthenticationError, CommunicationError
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.kem.const import SCAN_INTERVAL_MINUTES
from homeassistant.components.kem.coordinator import MAX_RETRIES
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_retries(
    hass: HomeAssistant,
    platform_sensor,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    kem_config_entry: MockConfigEntry,
    generator: dict[str, any],
    mock_kem: AioKem,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the KEM sensors."""

    # Test a retryable error
    mock_kem.get_generator_data.reset_mock()
    mock_kem.get_generator_data.side_effect = CommunicationError("Comms error")
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(timedelta(minutes=SCAN_INTERVAL_MINUTES))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem.get_generator_data.call_count == MAX_RETRIES

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test a non-retryable error
    mock_kem.get_generator_data.reset_mock()
    mock_kem.get_generator_data.side_effect = Exception("An exception")
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(timedelta(minutes=SCAN_INTERVAL_MINUTES))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem.get_generator_data.call_count == 1

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Test an authentication error
    # This should result in reauthenticating.
    mock_kem.authenticate.reset_mock()
    mock_kem.get_generator_data.reset_mock()
    mock_kem.get_generator_data.side_effect = [
        AuthenticationError("An exception"),
        generator,
    ]
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(timedelta(minutes=SCAN_INTERVAL_MINUTES))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem.get_generator_data.call_count == 2
    assert mock_kem.authenticate.call_count == 1

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == "Standby"

    # Test a persistent authentication error
    # This should result in failure with no retries.
    mock_kem.authenticate.reset_mock()
    mock_kem.authenticate.side_effect = AuthenticationError("Unauthorized")
    mock_kem.get_generator_data.reset_mock()
    mock_kem.get_generator_data.side_effect = [
        AuthenticationError("An exception"),
        generator,
    ]
    mock_retry_delay = [0, 0, 0]
    with patch(
        "homeassistant.components.kem.coordinator.RETRY_DELAY", mock_retry_delay
    ):
        freezer.tick(timedelta(minutes=SCAN_INTERVAL_MINUTES))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_kem.get_generator_data.call_count == 1
    assert mock_kem.authenticate.call_count == 1

    state = hass.states.get("sensor.generator_1_engine_state")
    assert state
    assert state.state == STATE_UNAVAILABLE
