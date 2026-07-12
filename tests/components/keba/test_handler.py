"""Tests for the KebaHandler class."""

from unittest.mock import AsyncMock, MagicMock, patch

from keba_kecontact.connection import KebaKeContact
import pytest

from homeassistant.components.keba import KebaHandler
from homeassistant.components.keba.const import (
    CONF_FS_FALLBACK,
    CONF_FS_PERSIST,
    CONF_FS_TIMEOUT,
    MAX_FAST_POLLING_COUNT,
    MAX_POLLING_INTERVAL,
)


def _make_handler() -> KebaHandler:
    """Construct a KebaHandler with all external dependencies stubbed out."""
    # KebaKeContact uses SingletonMeta; reset so each call gets a new instance.
    KebaHandler._instance = None

    mock_hass = MagicMock()
    mock_hass.loop.create_task.return_value = MagicMock()

    with patch.object(KebaKeContact, "__init__", return_value=None):
        h = KebaHandler(mock_hass, "192.168.1.100", "test_rfid")

    h.keba_protocol = None
    h.request_data = AsyncMock()
    h.get_value = MagicMock(side_effect={"Serial": "12345678", "Product": "KC-P30"}.get)
    h.set_energy = AsyncMock()
    h.set_current = AsyncMock()
    h.start = AsyncMock()
    h.stop = AsyncMock()
    h.enable = AsyncMock()
    h.set_failsafe = AsyncMock()
    h.set_text = AsyncMock()
    return h


@pytest.fixture
def handler() -> KebaHandler:
    """Provide a fresh KebaHandler per test with no shared state."""
    return _make_handler()


async def test_init(handler: KebaHandler) -> None:
    """Test KebaHandler attributes after construction."""
    assert handler.rfid == "test_rfid"
    assert handler.device_name == "keba"
    assert handler.device_id == "keba_wallbox_"
    assert handler._polling_task is None
    assert handler._update_listeners == []


async def test_setup_success(handler: KebaHandler) -> None:
    """Test setup returns True when the charger reports its serial and product."""
    with patch.object(KebaKeContact, "setup", new_callable=AsyncMock, create=True):
        result = await handler.setup()

    assert result is True
    assert handler.device_id == "keba_wallbox_12345678"
    assert handler.device_name == "KC-P30"


async def test_setup_no_serial(handler: KebaHandler) -> None:
    """Test setup returns False when no serial is available."""
    handler.get_value = MagicMock(return_value=None)
    with patch.object(KebaKeContact, "setup", new_callable=AsyncMock, create=True):
        result = await handler.setup()

    assert result is False


async def test_start_periodic_request(handler: KebaHandler) -> None:
    """Test that start_periodic_request stores a polling task."""
    handler.start_periodic_request()

    handler._hass.loop.create_task.assert_called_once()
    assert handler._polling_task is not None
    # Close the unawaited coroutine to avoid ResourceWarning
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_stop_periodic_request_cancels_task(handler: KebaHandler) -> None:
    """Test stop_periodic_request cancels the polling task."""
    handler.start_periodic_request()
    mock_task = handler._polling_task
    handler._hass.loop.create_task.call_args[0][0].close()

    handler.stop_periodic_request()

    mock_task.cancel.assert_called_once()
    assert handler._polling_task is None


async def test_stop_periodic_request_closes_transport(handler: KebaHandler) -> None:
    """Test stop_periodic_request closes the UDP transport when present."""
    mock_transport = MagicMock()
    mock_protocol = MagicMock()
    mock_protocol._transport = mock_transport
    handler.keba_protocol = mock_protocol

    handler.stop_periodic_request()
    mock_transport.close.assert_called_once()


async def test_stop_periodic_request_no_task(handler: KebaHandler) -> None:
    """Test stop_periodic_request is safe when no task is running."""
    assert handler._polling_task is None
    handler.stop_periodic_request()  # must not raise


async def test_periodic_request_fast_polling(handler: KebaHandler) -> None:
    """Test _periodic_request uses the short sleep in fast-polling mode."""
    handler._fast_polling_count = 0

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await handler._periodic_request()

    handler.request_data.assert_called_once()
    mock_sleep.assert_called_once_with(2)
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_periodic_request_slow_polling(handler: KebaHandler) -> None:
    """Test _periodic_request uses the long sleep when fast-polling count is maxed."""
    handler._fast_polling_count = MAX_FAST_POLLING_COUNT

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await handler._periodic_request()

    mock_sleep.assert_called_once_with(MAX_POLLING_INTERVAL)
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_hass_callback(handler: KebaHandler) -> None:
    """Test hass_callback notifies all registered listeners."""
    called: list[int] = []
    handler._update_listeners = [lambda: called.append(1), lambda: called.append(2)]
    handler.hass_callback({})
    assert called == [1, 2]


async def test_set_fast_polling_with_task(handler: KebaHandler) -> None:
    """Test _set_fast_polling cancels the existing task and resets the counter."""
    mock_task = MagicMock()
    handler._polling_task = mock_task
    handler._fast_polling_count = MAX_FAST_POLLING_COUNT

    handler._set_fast_polling()

    assert handler._fast_polling_count == 0
    mock_task.cancel.assert_called_once()
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_set_fast_polling_no_task(handler: KebaHandler) -> None:
    """Test _set_fast_polling works when no task is currently running."""
    assert handler._polling_task is None

    handler._set_fast_polling()

    assert handler._fast_polling_count == 0
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_add_update_listener(handler: KebaHandler) -> None:
    """Test add_update_listener appends and immediately invokes the listener."""
    called: list[int] = []
    handler.add_update_listener(lambda: called.append(1))
    assert len(handler._update_listeners) == 1
    assert called == [1]


async def test_async_request_data(handler: KebaHandler) -> None:
    """Test async_request_data delegates to the base request_data method."""
    await handler.async_request_data({})
    handler.request_data.assert_called_once()


async def test_async_set_energy_valid(handler: KebaHandler) -> None:
    """Test async_set_energy calls set_energy with a valid float value."""
    handler._polling_task = MagicMock()

    await handler.async_set_energy({"energy": "10.0"})

    handler.set_energy.assert_called_once_with(10.0)
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_async_set_energy_invalid(handler: KebaHandler) -> None:
    """Test async_set_energy with a missing key does not raise."""
    await handler.async_set_energy({})
    handler.set_energy.assert_not_called()


async def test_async_set_current_valid(handler: KebaHandler) -> None:
    """Test async_set_current calls set_current with a valid float value."""
    await handler.async_set_current({"current": "16.0"})
    handler.set_current.assert_called_once_with(16.0)


async def test_async_set_current_invalid(handler: KebaHandler) -> None:
    """Test async_set_current with a missing key does not raise."""
    await handler.async_set_current({})
    handler.set_current.assert_not_called()


async def test_async_start(handler: KebaHandler) -> None:
    """Test async_start authorizes via RFID and triggers fast polling."""
    handler._polling_task = MagicMock()

    await handler.async_start()

    handler.start.assert_called_once_with("test_rfid")
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_async_stop(handler: KebaHandler) -> None:
    """Test async_stop deauthorizes via RFID and triggers fast polling."""
    handler._polling_task = MagicMock()

    await handler.async_stop()

    handler.stop.assert_called_once_with("test_rfid")
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_async_enable_ev(handler: KebaHandler) -> None:
    """Test async_enable_ev enables charging and triggers fast polling."""
    handler._polling_task = MagicMock()

    await handler.async_enable_ev()

    handler.enable.assert_called_once_with(True)
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_async_disable_ev(handler: KebaHandler) -> None:
    """Test async_disable_ev disables charging and triggers fast polling."""
    handler._polling_task = MagicMock()

    await handler.async_disable_ev()

    handler.enable.assert_called_once_with(False)
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_async_set_failsafe_valid(handler: KebaHandler) -> None:
    """Test async_set_failsafe calls set_failsafe with valid parameters."""
    handler._polling_task = MagicMock()

    await handler.async_set_failsafe(
        {CONF_FS_TIMEOUT: 30, CONF_FS_FALLBACK: 6.0, CONF_FS_PERSIST: 0}
    )

    handler.set_failsafe.assert_called_once_with(30, 6.0, False)
    handler._hass.loop.create_task.call_args[0][0].close()


async def test_async_set_failsafe_invalid(handler: KebaHandler) -> None:
    """Test async_set_failsafe with missing parameters does not raise."""
    await handler.async_set_failsafe({})
    handler.set_failsafe.assert_not_called()
