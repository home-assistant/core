"""Test the Sofar Inverter Modbus coordinator's timeout-recovery behavior."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError

from homeassistant.components.sofar_modbus.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "switch.4_4_ktlx_g3_active_power_control"


async def test_disconnects_after_repeated_timeouts(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
) -> None:
    """Test the coordinator recycles the connection after consecutive timeouts."""
    coordinator = init_integration.runtime_data
    unit = coordinator.connection.for_unit(1)
    unit.fail_requests(ModbusTimeoutError("stuck"))

    with patch.object(
        coordinator.connection, "disconnect", wraps=coordinator.connection.disconnect
    ) as mock_disconnect:
        for _ in range(3):
            freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (state := hass.states.get(ENTITY_ID))
            assert state.state == STATE_UNAVAILABLE

        assert mock_disconnect.await_count == 1


async def test_consecutive_timeouts_resets_on_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
) -> None:
    """Test a successful poll resets the timeout counter before the disconnect threshold."""
    coordinator = init_integration.runtime_data
    unit = coordinator.connection.for_unit(1)

    with patch.object(
        coordinator.connection, "disconnect", wraps=coordinator.connection.disconnect
    ) as mock_disconnect:
        unit.fail_requests(ModbusTimeoutError("stuck"))
        for _ in range(2):
            freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (state := hass.states.get(ENTITY_ID))
            assert state.state == STATE_UNAVAILABLE
        assert mock_disconnect.await_count == 0

        unit.fail_requests(None)
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (state := hass.states.get(ENTITY_ID))
        assert state.state == STATE_OFF

        # Two more timeouts alone shouldn't hit the threshold if the counter
        # actually reset on the successful poll above.
        unit.fail_requests(ModbusTimeoutError("stuck"))
        for _ in range(2):
            freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (state := hass.states.get(ENTITY_ID))
            assert state.state == STATE_UNAVAILABLE
        assert mock_disconnect.await_count == 0
