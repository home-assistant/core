"""WebSocket client for Hidromotic flooding system."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any

import aiohttp

from .const import (
    OUTPUT_TYPE_TANQUE,
    OUTPUT_TYPE_ZONA,
    STATE_DISABLED,
    TANK_EMPTY,
    TANK_FULL,
)

_LOGGER = logging.getLogger(__name__)


def hex_to_int(h: str) -> int:
    """Convert hex character to int (handles A, B, C for 10, 11, 12)."""
    if h == "A":
        return 10
    if h == "B":
        return 11
    if h == "C":
        return 12
    return int(h)


def int_to_hex(i: int) -> str:
    """Convert int to hex character (handles 10, 11, 12 as A, B, C)."""
    if i == 10:
        return "A"
    if i == 11:
        return "B"
    if i == 12:
        return "C"
    return str(i)


class HidromoticClient:
    """WebSocket client for Hidromotic device."""

    RECONNECT_INTERVAL = 30  # seconds

    def __init__(self, host: str) -> None:
        """Initialize the client."""
        self.host = host
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._connected = False
        self._should_reconnect = True
        self._reconnect_task: asyncio.Task | None = None
        self._listener_task: asyncio.Task | None = None
        self._data: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._output_tipo_map: dict[int, int] = {}  # Maps tipo to output_id

    @property
    def connected(self) -> bool:
        """Return if connected to device."""
        return self._connected

    @property
    def data(self) -> dict[str, Any]:
        """Return current device data."""
        return self._data

    def register_callback(
        self, callback: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a callback for data updates."""
        self._callbacks.append(callback)
        return lambda: self._callbacks.remove(callback)

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            if self._session is None:
                self._session = aiohttp.ClientSession()

            url = f"ws://{self.host}/rpc"
            _LOGGER.debug("Connecting to %s", url)
            self._ws = await self._session.ws_connect(url, heartbeat=30)
            self._connected = True
            _LOGGER.info("Connected to Hidromotic at %s", self.host)

            # Start listener task
            self._listener_task = asyncio.create_task(self._listen())

            # Send initial handshake command
            await self._send_command("e")

            # Wait a moment then request full configuration
            await asyncio.sleep(1)
            await self._send_command("#@C;")
            return True
        except Exception as err:
            _LOGGER.error("Failed to connect to Hidromotic: %s", err)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        self._should_reconnect = False
        self._connected = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
            self._session = None

    async def _send_command(self, command: str) -> None:
        """Send a command to the device using JSON-RPC format."""
        if not self._ws or self._ws.closed:
            _LOGGER.warning("Cannot send command, not connected")
            return
        async with self._lock:
            # Device uses JSON-RPC format
            # Commands starting with # don't need id field
            if command.startswith("#"):
                payload = f'{{"method":"hdmt","params":{{"c":"{command}"}}}}'
            else:
                payload = f'{{"id":1111,"method":"hdmt","params":{{"c":"{command}"}}}}'
            _LOGGER.debug("Sending command: %s", payload)
            await self._ws.send_str(payload)

    async def _listen(self) -> None:
        """Listen for messages from the device."""
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await self._process_binary(msg.data)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    await self._process_text(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", msg.data)
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    _LOGGER.info("WebSocket closed")
                    break
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.error("Error in WebSocket listener: %s", err)
        finally:
            self._connected = False
            # Schedule reconnection if needed
            if self._should_reconnect:
                self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the device."""
        while self._should_reconnect and not self._connected:
            _LOGGER.info(
                "Attempting to reconnect to Hidromotic in %d seconds",
                self.RECONNECT_INTERVAL,
            )
            await asyncio.sleep(self.RECONNECT_INTERVAL)
            if not self._should_reconnect:
                break
            try:
                if await self.connect():
                    _LOGGER.info("Reconnected to Hidromotic")
                    break
            except Exception as err:
                _LOGGER.debug("Reconnection attempt failed: %s", err)

    async def _process_text(self, data: str) -> None:
        """Process text message (JSON)."""
        try:
            parsed = json.loads(data)
            _LOGGER.debug("Received JSON: %s", parsed)
        except Exception:
            _LOGGER.debug("Non-JSON text received: %s", data)

    async def _process_binary(self, data: bytes) -> None:
        """Process binary message from device."""
        if len(data) < 2:
            return

        cmd = chr(data[0])
        _LOGGER.debug("Processing binary command: %s, length: %d", cmd, len(data))

        if cmd == "C":
            # Full configuration data
            await self._parse_full_config(data)
        elif cmd == "D":
            # Running data update
            await self._parse_running_data(data)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._data)
            except Exception as err:
                _LOGGER.error("Error in callback: %s", err)

    async def _parse_full_config(self, data: bytes) -> None:
        """Parse full configuration data (command 'C')."""
        is_mini = data[1] == 77  # 'M' = 77
        max_outputs = 6 if is_mini else 12

        self._data["is_mini"] = is_mini
        self._data["pic_version"] = data[2] | (data[3] << 8)
        self._data["pic_id"] = f"0x{data[6]:02X}"

        _LOGGER.debug(
            "Parsing config: is_mini=%s, pic_version=%s, data_len=%d",
            is_mini,
            self._data["pic_version"],
            len(data),
        )

        # Initialize data structures
        self._data["zones"] = {}
        self._data["tanks"] = {}
        self._data["pump"] = {}
        self._data["outputs"] = {}
        self._data["auto_riego"] = True  # Default to enabled

        # Find section markers by scanning
        b_pos = None
        s_pos = None
        for idx in range(16, len(data)):
            if data[idx] == 0x42 and b_pos is None:  # 'B'
                b_pos = idx
            elif data[idx] == 0x53 and s_pos is None:  # 'S'
                s_pos = idx
                break  # Found both, stop scanning

        _LOGGER.debug("Found sections: B at %s, S at %s", b_pos, s_pos)

        # Parse pump data if found
        if b_pos is not None and b_pos + 2 < len(data):
            self._data["pump"] = {
                "estado": data[b_pos + 1],
                "pausa_externa": data[b_pos + 2],
            }
            _LOGGER.debug("Pump data: %s", self._data["pump"])

        # Parse outputs starting from 'S' marker
        if s_pos is None:
            _LOGGER.warning("No 'S' section marker found in config data")
            return

        # Parse outputs starting after S marker, tracking slot IDs properly
        # Device has 12 output slots (0-11), some may be disabled
        i = s_pos + 1
        slot_id = 0

        _LOGGER.debug("Parsing outputs from position %d", i)

        while i < len(data) - 6 and slot_id < max_outputs:
            tipo = data[i]

            # Check if this is a disabled slot (tipo=0, estado=7)
            if tipo == 0x00:
                estado = data[i + 4] if i + 4 < len(data) else 0
                if estado == STATE_DISABLED:
                    _LOGGER.debug("Slot %d: disabled at pos %d", slot_id, i)
                    i += 6  # Disabled outputs have no label
                    slot_id += 1
                    continue
                # Not a disabled slot pattern, skip this byte
                i += 1
                continue

            # Check for valid zone or tank
            is_zone = 0x41 <= tipo <= 0x4C
            is_tank = 0x21 <= tipo <= 0x2C

            if not (is_zone or is_tank):
                i += 1
                continue

            # Validate output structure
            if i + 5 >= len(data):
                break

            bomba = data[i + 1]
            duracion = data[i + 2] | (data[i + 3] << 8)
            estado = data[i + 4]
            label_len = data[i + 5]

            # Sanity check
            if bomba > 1 or estado > STATE_DISABLED:
                i += 1
                continue

            # Read label
            label = ""
            if 0 < label_len <= 32 and i + 6 + label_len <= len(data):
                try:
                    label = data[i + 6 : i + 6 + label_len].decode(
                        "utf-8", errors="ignore"
                    )
                except Exception:
                    label = ""
                    label_len = 0
            else:
                label_len = 0

            tipo_id = (tipo & 0x0F) - 1

            output_data = {
                "id": tipo_id,
                "slot_id": slot_id,  # Actual device slot ID for commands
                "tipo": f"{tipo:02X}",
                "bomba": bomba,
                "duracion": duracion,
                "estado": estado,
                "label": label,
            }

            _LOGGER.debug(
                "Slot %d at pos %d: tipo=%s, estado=%d, label=%s",
                slot_id,
                i,
                output_data["tipo"],
                estado,
                label,
            )

            # Move past this output
            i += 6 + label_len
            slot_id += 1

            # Skip disabled outputs from entity creation
            if estado == STATE_DISABLED:
                continue

            self._data["outputs"][slot_id - 1] = output_data

            if is_zone:
                self._data["zones"][tipo_id] = {
                    "id": tipo_id,
                    "slot_id": output_data["slot_id"],
                    "estado": estado,
                    "label": label or f"Zone {tipo_id + 1}",
                    "duracion": duracion,
                }
            elif is_tank:
                self._data["tanks"][tipo_id] = {
                    "id": tipo_id,
                    "slot_id": output_data["slot_id"],
                    "estado": estado,
                    "label": label or f"Tank {tipo_id + 1}",
                    "nivel": 0xFF,
                    "modo": 0,
                }

        _LOGGER.debug(
            "Parsed data: zones=%s, tanks=%s",
            list(self._data["zones"].keys()),
            list(self._data["tanks"].keys()),
        )

    async def _parse_running_data(self, data: bytes) -> None:
        """Parse running data update (command 'D')."""
        i = 6
        while i < len(data):
            section = chr(data[i])

            if section == "B":
                self._data["pump"]["estado"] = data[i + 1]
                self._data["pump"]["pausa_externa"] = data[i + 2]
                i += 6

            elif section == "S":
                if i + 2 < len(data):
                    tipo = data[i + 1]
                    estado = data[i + 2]
                    # Find the output by tipo
                    for output_id, output in self._data.get("outputs", {}).items():
                        if int(output["tipo"], 16) == tipo:
                            output["estado"] = estado
                            # Update zone/tank estado
                            tipo_upper = tipo & 0xF0
                            tipo_id = (tipo & 0x0F) - 1
                            if (
                                tipo_upper == OUTPUT_TYPE_ZONA
                                and tipo_id in self._data.get("zones", {})
                            ):
                                self._data["zones"][tipo_id]["estado"] = estado
                            elif (
                                tipo_upper == OUTPUT_TYPE_TANQUE
                                and tipo_id in self._data.get("tanks", {})
                            ):
                                self._data["tanks"][tipo_id]["estado"] = estado
                                # Tank also has nivel
                                if i + 3 < len(data):
                                    self._data["tanks"][tipo_id]["nivel"] = data[i + 3]
                            break
                i += 3

            else:
                i += 1

    async def set_zone_state(self, zone_id: int, on: bool) -> None:
        """Turn a zone on or off."""
        zone = self._data.get("zones", {}).get(zone_id)
        if not zone:
            _LOGGER.warning("Zone %d not found", zone_id)
            return

        slot_id = zone["slot_id"]
        state = 1 if on else 0
        command = f"#@S{int_to_hex(slot_id)}M{state};"
        _LOGGER.debug("Setting zone %d (slot %d) to %s", zone_id, slot_id, state)
        await self._send_command(command)

    async def set_tank_state(self, tank_id: int, on: bool) -> None:
        """Turn a tank on or off."""
        tank = self._data.get("tanks", {}).get(tank_id)
        if not tank:
            _LOGGER.warning("Tank %d not found", tank_id)
            return

        slot_id = tank["slot_id"]
        state = 1 if on else 0
        command = f"#@S{int_to_hex(slot_id)}M{state};"
        _LOGGER.debug("Setting tank %d (slot %d) to %s", tank_id, slot_id, state)
        await self._send_command(command)

    async def refresh(self) -> None:
        """Request fresh data from device."""
        await self._send_command("#@C;")

    def get_zones(self) -> dict[int, dict[str, Any]]:
        """Get all active zones."""
        return self._data.get("zones", {})

    def get_tanks(self) -> dict[int, dict[str, Any]]:
        """Get all active tanks."""
        return self._data.get("tanks", {})

    def get_pump(self) -> dict[str, Any]:
        """Get pump status."""
        return self._data.get("pump", {})

    def is_auto_riego_on(self) -> bool:
        """Check if auto riego is enabled."""
        return self._data.get("auto_riego", False)

    async def set_auto_riego(self, on: bool) -> None:
        """Enable or disable auto riego."""
        state = 1 if on else 0
        command = f"#@RA{state};"
        await self._send_command(command)
        # Update local state optimistically
        self._data["auto_riego"] = on
        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self._data)
            except Exception as err:
                _LOGGER.error("Error in callback: %s", err)

    def is_zone_on(self, zone_id: int) -> bool:
        """Check if a zone is on."""
        zone = self._data.get("zones", {}).get(zone_id)
        if zone:
            return zone.get("estado", 0) == 1
        return False

    def is_tank_full(self, tank_id: int) -> bool:
        """Check if a tank is full."""
        tank = self._data.get("tanks", {}).get(tank_id)
        if tank:
            return tank.get("nivel", 0xFF) == TANK_FULL
        return False

    def is_tank_empty(self, tank_id: int) -> bool:
        """Check if a tank is empty."""
        tank = self._data.get("tanks", {}).get(tank_id)
        if tank:
            return tank.get("nivel", 0xFF) == TANK_EMPTY
        return False

    def get_tank_level(self, tank_id: int) -> str:
        """Get tank level as string."""
        tank = self._data.get("tanks", {}).get(tank_id)
        if not tank:
            return "unknown"
        nivel = tank.get("nivel", 0xFF)
        if nivel == TANK_FULL:
            return "full"
        if nivel == TANK_EMPTY:
            return "empty"
        if nivel == 2:
            return "sensor_fail"
        if nivel == 3:
            return "level_fail"
        if nivel == 4:
            return "medium"
        return "unknown"
