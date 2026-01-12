"""Tests for the Hidromotic WebSocket client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.hidromotic.client import (
    HidromoticClient,
    hex_to_int,
    int_to_hex,
)


class TestHexConversion:
    """Tests for hex conversion helper functions."""

    def test_hex_to_int_digits(self) -> None:
        """Test hex_to_int with digit characters."""
        assert hex_to_int("0") == 0
        assert hex_to_int("1") == 1
        assert hex_to_int("5") == 5
        assert hex_to_int("9") == 9

    def test_hex_to_int_letters(self) -> None:
        """Test hex_to_int with letter characters."""
        assert hex_to_int("A") == 10
        assert hex_to_int("B") == 11
        assert hex_to_int("C") == 12

    def test_int_to_hex_digits(self) -> None:
        """Test int_to_hex with digit values."""
        assert int_to_hex(0) == "0"
        assert int_to_hex(1) == "1"
        assert int_to_hex(5) == "5"
        assert int_to_hex(9) == "9"

    def test_int_to_hex_letters(self) -> None:
        """Test int_to_hex with letter values."""
        assert int_to_hex(10) == "A"
        assert int_to_hex(11) == "B"
        assert int_to_hex(12) == "C"


class TestHidromoticClient:
    """Tests for the HidromoticClient class."""

    def test_init(self) -> None:
        """Test client initialization."""
        client = HidromoticClient("192.168.1.100")
        assert client.host == "192.168.1.100"
        assert client.connected is False
        assert client.data == {}

    def test_data_property(self) -> None:
        """Test data property returns internal data."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"test": "value"}
        assert client.data == {"test": "value"}

    def test_connected_property(self) -> None:
        """Test connected property."""
        client = HidromoticClient("192.168.1.100")
        assert client.connected is False
        client._connected = True
        assert client.connected is True

    def test_register_callback(self) -> None:
        """Test registering a callback."""
        client = HidromoticClient("192.168.1.100")
        callback = MagicMock()

        unregister = client.register_callback(callback)
        assert callback in client._callbacks

        unregister()
        assert callback not in client._callbacks

    def test_get_zones(self) -> None:
        """Test get_zones returns zones data."""
        client = HidromoticClient("192.168.1.100")
        client._data = {
            "zones": {
                0: {"id": 0, "estado": 0},
                1: {"id": 1, "estado": 1},
            }
        }
        zones = client.get_zones()
        assert len(zones) == 2
        assert 0 in zones
        assert 1 in zones

    def test_get_zones_empty(self) -> None:
        """Test get_zones returns empty dict when no zones."""
        client = HidromoticClient("192.168.1.100")
        assert client.get_zones() == {}

    def test_get_tanks(self) -> None:
        """Test get_tanks returns tanks data."""
        client = HidromoticClient("192.168.1.100")
        client._data = {
            "tanks": {
                0: {"id": 0, "nivel": 0},
            }
        }
        tanks = client.get_tanks()
        assert len(tanks) == 1
        assert 0 in tanks

    def test_get_tanks_empty(self) -> None:
        """Test get_tanks returns empty dict when no tanks."""
        client = HidromoticClient("192.168.1.100")
        assert client.get_tanks() == {}

    def test_get_pump(self) -> None:
        """Test get_pump returns pump data."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"pump": {"estado": 1, "pausa_externa": 0}}
        pump = client.get_pump()
        assert pump["estado"] == 1
        assert pump["pausa_externa"] == 0

    def test_get_pump_empty(self) -> None:
        """Test get_pump returns empty dict when no pump data."""
        client = HidromoticClient("192.168.1.100")
        assert client.get_pump() == {}

    def test_is_zone_on_true(self) -> None:
        """Test is_zone_on returns True when zone is on."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"zones": {0: {"id": 0, "estado": 1}}}
        assert client.is_zone_on(0) is True

    def test_is_zone_on_false(self) -> None:
        """Test is_zone_on returns False when zone is off."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"zones": {0: {"id": 0, "estado": 0}}}
        assert client.is_zone_on(0) is False

    def test_is_zone_on_not_found(self) -> None:
        """Test is_zone_on returns False when zone not found."""
        client = HidromoticClient("192.168.1.100")
        assert client.is_zone_on(99) is False

    def test_is_auto_riego_on_true(self) -> None:
        """Test is_auto_riego_on returns True when enabled."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"auto_riego": True}
        assert client.is_auto_riego_on() is True

    def test_is_auto_riego_on_false(self) -> None:
        """Test is_auto_riego_on returns False when disabled."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"auto_riego": False}
        assert client.is_auto_riego_on() is False

    def test_is_auto_riego_on_default(self) -> None:
        """Test is_auto_riego_on returns False when not set."""
        client = HidromoticClient("192.168.1.100")
        assert client.is_auto_riego_on() is False

    def test_is_tank_full_true(self) -> None:
        """Test is_tank_full returns True when tank is full."""
        client = HidromoticClient("192.168.1.100")
        client._data = {
            "tanks": {0: {"id": 0, "nivel": 0}}  # 0 = TANK_FULL
        }
        assert client.is_tank_full(0) is True

    def test_is_tank_full_false(self) -> None:
        """Test is_tank_full returns False when tank is not full."""
        client = HidromoticClient("192.168.1.100")
        client._data = {
            "tanks": {0: {"id": 0, "nivel": 1}}  # 1 = TANK_EMPTY
        }
        assert client.is_tank_full(0) is False

    def test_is_tank_full_not_found(self) -> None:
        """Test is_tank_full returns False when tank not found."""
        client = HidromoticClient("192.168.1.100")
        assert client.is_tank_full(99) is False

    def test_is_tank_empty_true(self) -> None:
        """Test is_tank_empty returns True when tank is empty."""
        client = HidromoticClient("192.168.1.100")
        client._data = {
            "tanks": {0: {"id": 0, "nivel": 1}}  # 1 = TANK_EMPTY
        }
        assert client.is_tank_empty(0) is True

    def test_is_tank_empty_false(self) -> None:
        """Test is_tank_empty returns False when tank is not empty."""
        client = HidromoticClient("192.168.1.100")
        client._data = {
            "tanks": {0: {"id": 0, "nivel": 0}}  # 0 = TANK_FULL
        }
        assert client.is_tank_empty(0) is False

    def test_is_tank_empty_not_found(self) -> None:
        """Test is_tank_empty returns False when tank not found."""
        client = HidromoticClient("192.168.1.100")
        assert client.is_tank_empty(99) is False

    def test_get_tank_level_full(self) -> None:
        """Test get_tank_level returns 'full' for full tank."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"tanks": {0: {"id": 0, "nivel": 0}}}
        assert client.get_tank_level(0) == "full"

    def test_get_tank_level_empty(self) -> None:
        """Test get_tank_level returns 'empty' for empty tank."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"tanks": {0: {"id": 0, "nivel": 1}}}
        assert client.get_tank_level(0) == "empty"

    def test_get_tank_level_sensor_fail(self) -> None:
        """Test get_tank_level returns 'sensor_fail'."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"tanks": {0: {"id": 0, "nivel": 2}}}
        assert client.get_tank_level(0) == "sensor_fail"

    def test_get_tank_level_level_fail(self) -> None:
        """Test get_tank_level returns 'level_fail'."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"tanks": {0: {"id": 0, "nivel": 3}}}
        assert client.get_tank_level(0) == "level_fail"

    def test_get_tank_level_medium(self) -> None:
        """Test get_tank_level returns 'medium'."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"tanks": {0: {"id": 0, "nivel": 4}}}
        assert client.get_tank_level(0) == "medium"

    def test_get_tank_level_unknown(self) -> None:
        """Test get_tank_level returns 'unknown' for unknown level."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"tanks": {0: {"id": 0, "nivel": 99}}}
        assert client.get_tank_level(0) == "unknown"

    def test_get_tank_level_not_found(self) -> None:
        """Test get_tank_level returns 'unknown' when tank not found."""
        client = HidromoticClient("192.168.1.100")
        assert client.get_tank_level(99) == "unknown"


class TestHidromoticClientAsync:
    """Async tests for the HidromoticClient class."""

    @pytest.mark.asyncio
    async def test_set_zone_state_on(self) -> None:
        """Test set_zone_state sends correct command to turn on."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"zones": {0: {"id": 0, "slot_id": 2, "estado": 0}}}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.set_zone_state(0, True)

        client._ws.send_str.assert_called_once_with(
            '{"method":"hdmt","params":{"c":"#@S2M1;"}}'
        )

    @pytest.mark.asyncio
    async def test_set_zone_state_off(self) -> None:
        """Test set_zone_state sends correct command to turn off."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"zones": {0: {"id": 0, "slot_id": 5, "estado": 1}}}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.set_zone_state(0, False)

        client._ws.send_str.assert_called_once_with(
            '{"method":"hdmt","params":{"c":"#@S5M0;"}}'
        )

    @pytest.mark.asyncio
    async def test_set_zone_state_hex_output(self) -> None:
        """Test set_zone_state uses hex for slot_id >= 10."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"zones": {0: {"id": 0, "slot_id": 10, "estado": 0}}}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.set_zone_state(0, True)

        client._ws.send_str.assert_called_once_with(
            '{"method":"hdmt","params":{"c":"#@SAM1;"}}'
        )

    @pytest.mark.asyncio
    async def test_set_zone_state_zone_not_found(self) -> None:
        """Test set_zone_state does nothing when zone not found."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"zones": {}}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.set_zone_state(99, True)

        client._ws.send_str.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_auto_riego_on(self) -> None:
        """Test set_auto_riego sends correct command to enable."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"auto_riego": False}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.set_auto_riego(True)

        client._ws.send_str.assert_called_once_with(
            '{"method":"hdmt","params":{"c":"#@RA1;"}}'
        )
        assert client._data["auto_riego"] is True

    @pytest.mark.asyncio
    async def test_set_auto_riego_off(self) -> None:
        """Test set_auto_riego sends correct command to disable."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"auto_riego": True}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.set_auto_riego(False)

        client._ws.send_str.assert_called_once_with(
            '{"method":"hdmt","params":{"c":"#@RA0;"}}'
        )
        assert client._data["auto_riego"] is False

    @pytest.mark.asyncio
    async def test_set_auto_riego_notifies_callbacks(self) -> None:
        """Test set_auto_riego notifies registered callbacks."""
        client = HidromoticClient("192.168.1.100")
        client._data = {"auto_riego": False}
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        callback = MagicMock()
        client.register_callback(callback)

        await client.set_auto_riego(True)

        callback.assert_called_once_with(client._data)

    @pytest.mark.asyncio
    async def test_refresh(self) -> None:
        """Test refresh sends correct command."""
        client = HidromoticClient("192.168.1.100")
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        await client.refresh()

        client._ws.send_str.assert_called_once_with(
            '{"method":"hdmt","params":{"c":"#@C;"}}'
        )

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        """Test disconnect closes connections properly."""
        client = HidromoticClient("192.168.1.100")
        client._connected = True

        # Create proper mocks for ws and session
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        client._ws = mock_ws

        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        client._session = mock_session

        await client.disconnect()

        assert client._connected is False
        assert client._should_reconnect is False
        mock_ws.close.assert_called_once()
        mock_session.close.assert_called_once()
        assert client._session is None
