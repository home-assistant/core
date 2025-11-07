"""UDP client for Marstek device communication."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import ipaddress
import json
import logging
import socket
from typing import Any

try:
    import psutil  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001 - optional dependency
    psutil = None  # type: ignore[assignment]

from homeassistant.core import HomeAssistant

from .command_builder import discover
from .const import DEFAULT_UDP_PORT, DISCOVERY_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class MarstekUDPClient:
    """UDP client for Marstek device communication."""

    def __init__(self, hass: HomeAssistant, port: int = DEFAULT_UDP_PORT) -> None:
        """Initialize UDP client."""
        self._hass = hass
        self._port = port
        self._socket: socket.socket | None = None
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._response_cache: dict[int, dict[str, Any]] = {}
        self._listen_task: asyncio.Task | None = None
        # Cache mechanism
        self._discovery_cache: list[dict[str, Any]] | None = None
        self._cache_timestamp: float = 0
        self._cache_duration: float = 30.0  # 30 second cache
        # Fixed local send IP (for logging and peer response identification)
        self._local_send_ip: str = "0.0.0.0"
        # Polling control mechanism
        self._polling_paused: dict[str, bool] = {}  # Track paused devices by IP
        self._polling_lock: asyncio.Lock = asyncio.Lock()

    async def async_setup(self) -> None:
        """Setup UDP socket."""
        if self._socket is not None:
            return

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)

        # Bind receive to 0.0.0.0:30000, fixed port
        self._socket.bind(("0.0.0.0", 30000))
        _LOGGER.debug(
            "UDP client bound to %s:%s",
            self._socket.getsockname()[0],
            self._socket.getsockname()[1],
        )

    async def async_cleanup(self) -> None:
        """Cleanup UDP socket."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listen_task

        if self._socket:
            self._socket.close()
            self._socket = None

    def _get_broadcast_addresses(self) -> list[str]:
        """Get broadcast address list, supports multiple network cards."""
        addresses = set()

        # Add global broadcast
        addresses.add("255.255.255.255")

        try:
            # Get all network interfaces
            if psutil is None:
                _LOGGER.warning("psutil not available, using only global broadcast")
            else:
                for addrs in psutil.net_if_addrs().values():
                    for addr in addrs:
                        if (
                            addr.family == socket.AF_INET
                            and not addr.address.startswith("127.")
                        ):
                            # Calculate broadcast address
                            if getattr(addr, "broadcast", None):
                                addresses.add(addr.broadcast)
                            else:
                                # If no broadcast address, calculate subnet broadcast
                                try:
                                    network = ipaddress.IPv4Network(
                                        f"{addr.address}/{addr.netmask}", strict=False
                                    )
                                    addresses.add(str(network.broadcast_address))
                                except (ValueError, OSError):
                                    pass
        except OSError as e:
            _LOGGER.warning("Failed to get network interfaces: %s", e)

        # Filter local addresses to avoid processing own responses
        try:
            if psutil is not None:
                local_ips = set()
                for addrs in psutil.net_if_addrs().values():
                    for addr in addrs:
                        if addr.family == socket.AF_INET:
                            local_ips.add(addr.address)
                addresses = addresses - local_ips
        except OSError:
            pass

        return list(addresses)

    def _is_cache_valid(self) -> bool:
        """Check if cache is valid."""
        if self._discovery_cache is None:
            return False
        current_time = asyncio.get_event_loop().time()
        return (current_time - self._cache_timestamp) < self._cache_duration

    def clear_discovery_cache(self) -> None:
        """Clear discovery cache."""
        self._discovery_cache = None
        self._cache_timestamp = 0
        _LOGGER.debug("Device discovery cache cleared")

    async def _send_udp_message(
        self, message: str, target_ip: str, target_port: int
    ) -> None:
        """Send UDP message to the specified target."""
        if not self._socket:
            await self.async_setup()

        try:
            data = message.encode("utf-8")
            self._socket.sendto(data, (target_ip, target_port))
            # Log send path with fixed local ip/port for readability
            _LOGGER.debug(
                "Send: %s:%d <- %s:%d | %s",
                target_ip,
                target_port,
                self._local_send_ip,
                self._port,
                message,
            )
        except Exception as err:
            _LOGGER.error("Failed to send UDP message: %s", err)
            raise

    async def send_request(
        self,
        message: str,
        target_ip: str,
        target_port: int,
        timeout: float = 5.0,
        *,
        quiet_on_timeout: bool = False,
    ) -> dict[str, Any]:
        """Send unicast request and wait for response."""
        if not self._socket:
            await self.async_setup()

        # Parse message to get ID
        try:
            message_obj = json.loads(message)
            request_id = message_obj["id"]
        except (json.JSONDecodeError, KeyError) as e:
            _LOGGER.error("Invalid message format: %s", e)
            raise ValueError(f"Invalid message format: {e}") from e

        # Create response collection Future
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # Start listening task (if not started)
            if not self._listen_task or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen_for_responses())

            # Send request
            await self._send_udp_message(message, target_ip, target_port)

            # Wait for response
            try:
                return await asyncio.wait_for(future, timeout=timeout)
            except TimeoutError as err:
                if quiet_on_timeout or self.is_polling_paused(target_ip):
                    _LOGGER.debug(
                        "Request timeout: %s:%d (quiet)", target_ip, target_port
                    )
                else:
                    _LOGGER.warning("Request timeout: %s:%d", target_ip, target_port)
                raise TimeoutError(
                    f"Request timeout to {target_ip}:{target_port}"
                ) from err

        finally:
            # Cleanup pending requests
            if request_id in self._pending_requests:
                self._pending_requests.pop(request_id, None)

    async def _listen_for_responses(self) -> None:
        """Listen for UDP responses."""
        if not self._socket:
            return

        loop = asyncio.get_event_loop()
        while True:
            try:
                data, addr = await loop.sock_recvfrom(self._socket, 4096)
                response_text = data.decode("utf-8")
                try:
                    response = json.loads(response_text)
                except json.JSONDecodeError:
                    response = {"raw": response_text}
                request_id = response.get("id") if isinstance(response, dict) else None

                # Log response path with fixed local ip/port for readability
                _LOGGER.debug(
                    "Recv: %s:%d -> %s:%d | %s",
                    addr[0],
                    addr[1],
                    self._local_send_ip,
                    self._port,
                    json.dumps(response, ensure_ascii=False),
                )

                # Store in response cache - reference Node.js hash table storage
                if request_id:
                    self._response_cache[request_id] = {
                        "response": response,
                        "addr": addr,
                        "timestamp": asyncio.get_event_loop().time(),
                    }

                # For unicast, resolve immediately
                if request_id and request_id in self._pending_requests:
                    future = self._pending_requests.pop(request_id)
                    if not future.done():
                        future.set_result(
                            response
                        )  # Return response directly, no wrapping

            except asyncio.CancelledError:
                break
            except OSError as err:
                _LOGGER.error("Error receiving UDP response: %s", err)
                await asyncio.sleep(1)

    async def send_broadcast_request(
        self, message: str, timeout: float = DISCOVERY_TIMEOUT
    ) -> list[dict[str, Any]]:
        """Send broadcast request and collect all responses."""
        if not self._socket:
            await self.async_setup()

        # Parse message to get ID
        try:
            message_obj = json.loads(message)
            request_id = message_obj["id"]
        except (json.JSONDecodeError, KeyError) as e:
            _LOGGER.error("Invalid message format: %s", e)
            return []

        responses = []
        start_time = asyncio.get_event_loop().time()

        # Create response collection Future
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # Start listening task
            if not self._listen_task or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen_for_responses())

            # Send broadcast request
            broadcast_addresses = self._get_broadcast_addresses()
            _LOGGER.debug("Broadcast targets: %s", broadcast_addresses)

            for address in broadcast_addresses:
                await self._send_udp_message(message, address, self._port)
                _LOGGER.debug("Sent to %s:%s", address, self._port)

            _LOGGER.debug("Broadcast to %d interfaces", len(broadcast_addresses))
            _LOGGER.debug("Broadcast payload: %s", message)
            _LOGGER.debug("Target port: %s", self._port)

            # Wait for responses - reference Node.js hash table polling
            _LOGGER.debug("Start waiting for responses, timeout: %d s", timeout)
            try:
                while (asyncio.get_event_loop().time() - start_time) < timeout:
                    # Check if there are new responses in cache
                    if request_id in self._response_cache:
                        cached_response = self._response_cache[request_id]
                        responses.append(cached_response["response"])
                        _LOGGER.debug(
                            "Broadcast ID:%s received %d response(s)",
                            request_id,
                            len(responses),
                        )
                        # Remove processed cached response
                        del self._response_cache[request_id]

                    # Wait a short time before checking again
                    await asyncio.sleep(0.1)

                    # Check if timeout
                    if (asyncio.get_event_loop().time() - start_time) >= timeout:
                        _LOGGER.debug("Broadcast ID:%s wait timeout", request_id)
                        break

            except OSError as e:
                _LOGGER.error("Error waiting for response: %s", e)

        finally:
            # Cleanup pending requests
            if request_id in self._pending_requests:
                self._pending_requests.pop(request_id, None)

        _LOGGER.info("Broadcast discovery finished, %d responses", len(responses))
        return responses

    async def discover_devices(self, use_cache: bool = True) -> list[dict[str, Any]]:
        """Discover Marstek devices on network, wait 10s to collect all responses and deduplicate."""
        # Check cache
        if use_cache and self._is_cache_valid():
            _LOGGER.debug("Using cached discovery results")
            return self._discovery_cache.copy()

        devices = []
        seen_devices = set()  # For deduplication, based on MAC or IP address

        try:
            # Send broadcast discovery request, wait 10s to collect all responses
            discover_command = discover()
            responses = await self.send_broadcast_request(discover_command)

            for response in responses:
                if response.get("result"):
                    # Parse device information
                    device_info = response["result"]

                    # Get device unique identifier (prefer IP address as MAC may be duplicate)
                    device_id = (
                        device_info.get("ip", "")
                        or device_info.get("ble_mac")
                        or device_info.get("wifi_mac")
                        or f"device_{int(asyncio.get_event_loop().time())}_{hash(str(device_info)) % 10000}"
                    )

                    # Deduplication check
                    if device_id in seen_devices:
                        _LOGGER.debug(
                            "Skip duplicate device: %s (IP: %s, BLE_MAC: %s, WiFi_MAC: %s)",
                            device_id,
                            device_info.get("ip"),
                            device_info.get("ble_mac"),
                            device_info.get("wifi_mac"),
                        )
                        continue

                    seen_devices.add(device_id)
                    _LOGGER.debug(
                        "Add device: %s (IP: %s, BLE_MAC: %s, WiFi_MAC: %s)",
                        device_id,
                        device_info.get("ip"),
                        device_info.get("ble_mac"),
                        device_info.get("wifi_mac"),
                    )

                    # Build complete device information
                    device = {
                        "id": device_info.get("id", 0),
                        "device_type": device_info.get(
                            "device", "Unknown"
                        ),  # Device type
                        "version": device_info.get("ver", 0),  # Version number
                        "wifi_name": device_info.get("wifi_name", ""),  # WiFi name
                        "ip": device_info.get("ip", ""),  # IP address
                        "wifi_mac": device_info.get("wifi_mac", ""),  # WiFi MAC
                        "ble_mac": device_info.get("ble_mac", ""),  # BLE MAC
                        "mac": device_info.get("wifi_mac")
                        or device_info.get("ble_mac", ""),  # Compatibility field
                        "model": device_info.get(
                            "device", "Unknown"
                        ),  # Compatibility field
                        "firmware": str(
                            device_info.get("ver", 0)
                        ),  # Compatibility field
                    }

                    devices.append(device)
                    _LOGGER.info(
                        "Discovered device: Type=%s, Version=%s, WiFi=%s, IP=%s, MAC=%s",
                        device["device_type"],
                        device["version"],
                        device["wifi_name"],
                        device["ip"],
                        device["mac"],
                    )

        except OSError as err:
            _LOGGER.error("Device discovery failed: %s", err)

        # Update cache
        self._discovery_cache = devices.copy()
        self._cache_timestamp = asyncio.get_event_loop().time()

        _LOGGER.info("Device discovery finished, %d unique devices", len(devices))
        return devices

    async def pause_polling(self, device_ip: str) -> None:
        """Pause polling for a specific device."""
        async with self._polling_lock:
            self._polling_paused[device_ip] = True
            _LOGGER.info("Polling paused for device: %s", device_ip)

    async def resume_polling(self, device_ip: str) -> None:
        """Resume polling for a specific device."""
        async with self._polling_lock:
            self._polling_paused[device_ip] = False
            _LOGGER.info("Polling resumed for device: %s", device_ip)

    def is_polling_paused(self, device_ip: str) -> bool:
        """Check if polling is paused for a specific device."""
        return self._polling_paused.get(device_ip, False)

    async def send_request_with_polling_control(
        self, message: str, target_ip: str, target_port: int, timeout: float = 5.0
    ) -> dict[str, Any]:
        """Send request with polling control - pause polling during request."""
        # Pause polling for this device
        await self.pause_polling(target_ip)

        try:
            # Send the request
            return await self.send_request(
                message, target_ip, target_port, timeout, quiet_on_timeout=True
            )
        finally:
            # Always resume polling, regardless of success or failure
            await self.resume_polling(target_ip)
