"""Test the Sofar Inverter Modbus coordinator's poll-failure handling."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from homeassistant.components.sofar.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_timeouts_mark_unavailable_and_recover(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test repeated timeouts fail the update, and a later poll recovers it."""
    coordinator = init_integration.runtime_data.readings
    unit = mock_connection.for_unit(1)

    unit.fail_requests(ModbusTimeoutError("stuck"))
    for _ in range(3):
        freezer.tick(timedelta(seconds=SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert not coordinator.last_update_success

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success


async def test_runtime_data_routes_components_to_their_own_coordinator(
    init_integration: MockConfigEntry,
) -> None:
    """Test served_components/coordinator_for span both coordinators."""
    runtime_data = init_integration.runtime_data
    device = runtime_data.readings.device

    assert "grid" in device.readings_components
    assert "active_power_control" in device.settings_components
    assert runtime_data.served_components == (
        frozenset(device.readings_components) | frozenset(device.settings_components)
    )

    assert runtime_data.coordinator_for("grid") is runtime_data.readings
    assert runtime_data.coordinator_for("active_power_control") is runtime_data.settings
