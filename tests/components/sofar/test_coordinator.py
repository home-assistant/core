"""Test the Sofar Inverter Modbus coordinator's poll-failure handling."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusConnectionError, ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from sofar_modbus.model import UpdateReport

from homeassistant.components.sofar.const import SCAN_INTERVAL
from homeassistant.components.sofar.coordinator import SofarDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry, async_fire_time_changed


def _coordinator_polling(
    hass: HomeAssistant, entry: MockConfigEntry, report: UpdateReport
) -> SofarDataUpdateCoordinator:
    """Build a coordinator whose poll returns a fixed report."""
    return SofarDataUpdateCoordinator(
        hass,
        entry,
        entry.runtime_data.readings.device,
        AsyncMock(return_value=report),
        timedelta(seconds=SCAN_INTERVAL),
    )


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


async def test_every_component_failing_fails_the_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a poll where every component errored fails the update."""
    coordinator = init_integration.runtime_data.readings

    mock_connection.for_unit(1).fail_requests(ModbusError("illegal data address"))
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception.__cause__, ExceptionGroup)


async def test_empty_report_fails_the_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test a poll that reports neither success nor failure fails the update."""
    coordinator = _coordinator_polling(hass, init_integration, UpdateReport(set(), {}))

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.__cause__ is None


async def test_retry_recovers_a_failed_component(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test a component that answers the retry counts as updated."""
    coordinator = _coordinator_polling(
        hass, init_integration, UpdateReport({"grid"}, {"pv_1_2": ModbusError("busy")})
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.updated == {"grid", "pv_1_2"}
    assert not coordinator.data.failed


async def test_link_dying_during_retry_fails_the_update(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a dead link surfacing on the retry fails the whole update."""
    coordinator = _coordinator_polling(
        hass, init_integration, UpdateReport({"grid"}, {"pv_1_2": ModbusError("busy")})
    )
    mock_connection.for_unit(1).fail_requests(ModbusConnectionError("link dropped"))

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
