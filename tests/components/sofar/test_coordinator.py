"""Test the Sofar Inverter Modbus coordinator's poll-failure handling."""

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from homeassistant.components.sofar.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_timeouts_mark_unavailable_and_recover(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test repeated timeouts fail the update, and a later poll recovers it."""
    coordinator = init_integration.runtime_data
    unit = mock_connection.for_unit(1)

    unit.fail_requests(ModbusTimeoutError("stuck"))
    for _ in range(3):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert not coordinator.last_update_success

    unit.fail_requests(None)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success
