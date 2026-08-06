"""Tests for NexBlue binary sensors."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_binary_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test boolean charger telemetry is exposed as binary sensors."""
    assert hass.states.get("binary_sensor.nb123456_cable_lock_state").state == "on"
    assert hass.states.get("binary_sensor.nb123456_availability").state == "on"


async def test_binary_sensors_unavailable_when_coordinator_update_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test a failed coordinator update makes binary sensors unavailable."""
    coordinator = init_integration.runtime_data
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.nb123456_cable_lock_state").state
        == "unavailable"
    )
