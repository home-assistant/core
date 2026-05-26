"""Tests for the Diesel Heater coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest

from homeassistant.components.diesel_heater.const import DOMAIN
from homeassistant.components.diesel_heater.coordinator import VevorHeaterCoordinator
from homeassistant.const import CONF_ADDRESS, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import TEST_ADDRESS

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device


@pytest.fixture
def mock_ble_device():
    """Return a mock BLEDevice."""
    return generate_ble_device(address=TEST_ADDRESS, name="Diesel Heater")


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_ble_device) -> VevorHeaterCoordinator:
    """Create a VevorHeaterCoordinator wired to a real hass instance."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        data={CONF_ADDRESS: TEST_ADDRESS, CONF_PIN: 1234},
    )
    entry.add_to_hass(hass)
    return VevorHeaterCoordinator(hass, mock_ble_device, entry)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


async def test_init_sets_address_and_passkey(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Coordinator stores address and PIN from the config entry."""
    assert coordinator.address == TEST_ADDRESS
    assert coordinator._passkey == 1234


async def test_init_registers_all_protocols(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """All six BLE protocols are registered after init."""
    assert set(coordinator._protocols.keys()) == {1, 2, 3, 4, 5, 6}


async def test_protocol_mode_starts_at_zero(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Protocol mode property starts at 0 (not yet detected)."""
    assert coordinator.protocol_mode == 0


# ---------------------------------------------------------------------------
# Stale data tolerance
# ---------------------------------------------------------------------------


async def test_save_and_restore_valid_data(coordinator: VevorHeaterCoordinator) -> None:
    """Valid sensor values are cached and can be restored."""
    coordinator.data["cab_temperature"] = 22.5
    coordinator.data["supply_voltage"] = 12.4
    coordinator._save_valid_data()

    coordinator._clear_sensor_values()
    assert coordinator.data["cab_temperature"] is None

    coordinator._restore_stale_data()
    assert coordinator.data["cab_temperature"] == 22.5
    assert coordinator.data["supply_voltage"] == 12.4


async def test_clear_sensor_values_resets_volatile_fields(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """_clear_sensor_values nulls all volatile fields."""
    coordinator.data["cab_temperature"] = 22
    coordinator.data["running_state"] = 1

    coordinator._clear_sensor_values()

    assert coordinator.data["cab_temperature"] is None
    assert coordinator.data["running_state"] is None


async def test_handle_connection_failure_keeps_values_during_tolerance(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Within the tolerance window, last-known values are preserved."""
    coordinator.data["cab_temperature"] = 20
    coordinator._save_valid_data()
    coordinator._clear_sensor_values()

    coordinator._handle_connection_failure(Exception("boom"))

    assert coordinator._consecutive_failures == 1
    assert coordinator.data["cab_temperature"] == 20  # restored from cache


async def test_handle_connection_failure_marks_offline_after_threshold(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """After max_stale_cycles, the heater is marked disconnected."""
    coordinator.data["connected"] = True
    coordinator.data["cab_temperature"] = 20

    for _ in range(coordinator._max_stale_cycles + 1):
        coordinator._handle_connection_failure(Exception("boom"))

    assert coordinator.data["connected"] is False
    assert coordinator.data["cab_temperature"] is None


# ---------------------------------------------------------------------------
# Command builders / async commands (mock _send_command)
# ---------------------------------------------------------------------------


async def test_async_turn_on_sends_command_3_1(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """async_turn_on issues command 3 with argument 1."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_turn_on()

    coordinator._send_command.assert_awaited_once_with(3, 1)


async def test_async_turn_off_sends_command_3_0(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """async_turn_off issues command 3 with argument 0."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_turn_off()

    coordinator._send_command.assert_awaited_once_with(3, 0)


async def test_async_set_temperature_clamped_to_range(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Target temperature is clamped to 8..36."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_temperature(100)
    coordinator._send_command.assert_awaited_with(4, 36)

    coordinator._send_command.reset_mock()
    await coordinator.async_set_temperature(-5)
    coordinator._send_command.assert_awaited_with(4, 8)


async def test_async_set_temperature_converts_to_fahrenheit(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """When the heater is in Fahrenheit mode, the value is converted."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    coordinator._heater_uses_fahrenheit = True

    await coordinator.async_set_temperature(20)  # 20°C -> 68°F

    coordinator._send_command.assert_awaited_with(4, 68)


async def test_async_set_level_clamped_to_range(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Level is clamped to 1..10."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_level(50)
    coordinator._send_command.assert_awaited_with(4, 10)

    coordinator._send_command.reset_mock()
    await coordinator.async_set_level(0)
    coordinator._send_command.assert_awaited_with(4, 1)


async def test_async_set_mode_clamped(coordinator: VevorHeaterCoordinator) -> None:
    """Running mode is clamped to 0..2 unless ventilation (3)."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_mode(5)
    coordinator._send_command.assert_awaited_with(2, 2)


async def test_async_set_mode_ventilation_requires_abba(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Ventilation mode (3) is rejected on non-ABBA devices."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    coordinator._protocol_mode = 1  # not ABBA

    await coordinator.async_set_mode(3)

    coordinator._send_command.assert_not_awaited()


async def test_async_set_heater_offset_clamped(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Heater offset is clamped to MIN/MAX bounds."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_heater_offset(999)
    args = coordinator._send_command.await_args
    assert args.args[0] == 20  # cmd 20
    assert args.args[1] <= 50  # clamped to MAX_HEATER_OFFSET (sensible upper bound)


async def test_async_set_tank_volume_clamped(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Tank volume index is clamped to 0..10."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_tank_volume(99)
    coordinator._send_command.assert_awaited_with(16, 10)


async def test_async_set_backlight_clamped(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Backlight level is clamped to 0..100."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_backlight(200)
    coordinator._send_command.assert_awaited_with(21, 100)


async def test_async_set_temp_unit_updates_state(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """Setting Fahrenheit unit updates the cached temperature unit."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    await coordinator.async_set_temp_unit(True)

    assert coordinator._heater_uses_fahrenheit is True
    assert coordinator.data["temp_unit"] == 1


async def test_async_send_raw_command_returns_result(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """async_send_raw_command returns the success flag from _send_command."""
    coordinator._send_command = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    result = await coordinator.async_send_raw_command(99, 42)

    assert result is True
    coordinator._send_command.assert_awaited_once_with(99, 42)


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


async def test_async_shutdown_cleans_up(coordinator: VevorHeaterCoordinator) -> None:
    """async_shutdown closes any open BLE connection."""
    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client.disconnect = AsyncMock()
    coordinator._client = mock_client

    await coordinator.async_shutdown()

    mock_client.disconnect.assert_awaited()


# ---------------------------------------------------------------------------
# Update loop
# ---------------------------------------------------------------------------


async def test_async_update_data_reconnects_when_disconnected(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """When client is not connected, _async_update_data tries to reconnect."""
    coordinator._client = None
    with (
        patch.object(
            coordinator,
            "_ensure_connected",
            new=AsyncMock(side_effect=BleakError("nope")),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()
    assert coordinator._consecutive_failures == 1


async def test_async_update_data_returns_cached_on_failure_within_window(
    coordinator: VevorHeaterCoordinator,
) -> None:
    """During the stale tolerance window, _async_update_data returns cached data."""
    coordinator.data["cab_temperature"] = 18
    coordinator._save_valid_data()

    mock_client = MagicMock()
    mock_client.is_connected = True
    coordinator._client = mock_client
    coordinator._send_command = AsyncMock(return_value=False)

    result = await coordinator._async_update_data()

    assert result is coordinator.data
    assert coordinator._consecutive_failures == 1
