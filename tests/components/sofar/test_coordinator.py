"""Test the Sofar Inverter Modbus coordinator's timeout-recovery behavior."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError

from homeassistant.components.sofar.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_disconnects_after_repeated_timeouts(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
) -> None:
    """Test the coordinator recycles the connection after consecutive timeouts."""
    coordinator = init_integration.runtime_data.readings
    unit = coordinator.connection.for_unit(1)
    unit.fail_requests(ModbusTimeoutError("stuck"))

    with patch.object(
        coordinator.connection, "disconnect", wraps=coordinator.connection.disconnect
    ) as mock_disconnect:
        for _ in range(3):
            freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert not coordinator.last_update_success

        assert mock_disconnect.await_count == 1


async def test_consecutive_timeouts_resets_on_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
) -> None:
    """Test a successful poll resets the timeout counter before disconnect."""
    coordinator = init_integration.runtime_data.readings
    unit = coordinator.connection.for_unit(1)

    with patch.object(
        coordinator.connection, "disconnect", wraps=coordinator.connection.disconnect
    ) as mock_disconnect:
        unit.fail_requests(ModbusTimeoutError("stuck"))
        for _ in range(2):
            freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert not coordinator.last_update_success
        assert mock_disconnect.await_count == 0

        unit.fail_requests(None)
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert coordinator.last_update_success

        # Two more timeouts alone shouldn't hit the threshold if the counter
        # actually reset on the successful poll above.
        unit.fail_requests(ModbusTimeoutError("stuck"))
        for _ in range(2):
            freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert not coordinator.last_update_success
        assert mock_disconnect.await_count == 0


async def test_runtime_data_routes_components_to_their_own_coordinator(
    init_integration: MockConfigEntry,
) -> None:
    """Test served_components/coordinator_for span both coordinators."""
    runtime_data = init_integration.runtime_data

    assert "grid" in runtime_data.readings.served_components
    assert "active_power_control" in runtime_data.settings.served_components
    assert runtime_data.served_components == (
        runtime_data.readings.served_components
        | runtime_data.settings.served_components
    )

    assert runtime_data.coordinator_for("grid") is runtime_data.readings
    assert runtime_data.coordinator_for("active_power_control") is runtime_data.settings
