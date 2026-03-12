"""Discovery scheduler for the HiVi Speaker integration."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta
import logging
import socket
import time

import aiohttp
from defusedxml import ElementTree as ET

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .const import SIGNAL_DEVICE_DISCOVERED
from .device import ConnectionStatus

_LOGGER = logging.getLogger(__name__)

SCAN_TOTAL_TIMEOUT = 5.0  # seconds
SOCKET_TIMEOUT = 1.0  # seconds
SEND_REPEAT = 3
MCAST_ADDR = ("239.255.255.250", 1900)


class HIVIDiscoveryScheduler:
    """Intelligent discovery scheduler."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
        device_manager,
        base_interval: int = 300,
    ) -> None:
        """Initialize the discovery scheduler."""
        self.hass = hass
        self.config_entry = config_entry
        self.device_manager = device_manager
        self.base_interval = base_interval  # 5-minute base interval

        # Dynamic adjustment
        self.current_interval = base_interval
        self.min_interval = 120  # Minimum 2 minutes
        self.max_interval = 600  # Maximum 10 minutes

        # Status flags
        self._discovery_task: asyncio.Task | None = None
        self._discovery_running = False
        self._next_discovery: datetime | None = None

        # Operation delay tracking
        self._operation_delays: dict[
            str, datetime
        ] = {}  # speaker_device_id -> operation time
        # Immediate discovery flag
        self._immediate_discovery_requested = False
        self._discovery_lock = asyncio.Lock()

        # Stop discovery
        self._discovery_unsub = None

    async def async_start(self):
        """Start scheduler."""

        _LOGGER.debug("Starting HIVI device discovery scheduler")

        if self._discovery_running:
            return

        self._discovery_running = True
        self._next_discovery = datetime.now()
        await self._reschedule()

    async def async_stop(self):
        """Stop scheduler."""
        _LOGGER.debug("Stopping HIVI device discovery scheduler")
        self._discovery_running = False
        if self._discovery_unsub:
            self._discovery_unsub()
            self._discovery_unsub = None

    async def _reschedule(self):
        """Reschedule discovery task (safe version)."""
        if not self._discovery_running or not self._next_discovery:
            _LOGGER.warning(
                "_reschedule not running or no next_discovery, stopping scheduling"
            )
            return

        # Cancel existing timer (if any)
        if getattr(self, "_discovery_unsub", None):
            try:
                _LOGGER.debug("_reschedule: canceling existing timer")
                self._discovery_unsub()
            except Exception:
                _LOGGER.exception("Error canceling existing timer")
            finally:
                self._discovery_unsub = None

        now = datetime.now()
        delay = (self._next_discovery - now).total_seconds()

        if delay <= 0:
            _LOGGER.debug("_reschedule: scheduling discovery immediately")
            try:
                self.hass.async_create_task(self._run_discovery())
            except Exception:
                _LOGGER.exception("Error scheduling _run_discovery immediately")
            return

        if delay < 0.1:
            _LOGGER.debug("_reschedule: clamping delay %s to 0.1s", delay)
            delay = 0.1

        _LOGGER.debug("_reschedule next discovery in %s seconds", delay)

        def _callback(_now):
            """Run discovery from async_call_later callback.

            Uses call_soon_threadsafe since callback may run in a non-event-loop thread.
            """
            _LOGGER.debug(
                "_reschedule callback triggered, create _run_discovery task (thread-safe)"
            )
            try:
                self.hass.loop.call_soon_threadsafe(
                    asyncio.create_task, self._run_discovery()
                )
            except Exception:
                _LOGGER.exception("Failed to create task in callback")

        try:
            self._discovery_unsub = async_call_later(self.hass, delay, _callback)
        except Exception:
            _LOGGER.exception(
                "Failed to register delayed callback, backing off for 60 seconds before retrying"
            )
            self._next_discovery = datetime.now() + timedelta(seconds=60)
            try:
                self._discovery_unsub = async_call_later(
                    self.hass,
                    60,
                    lambda _now: self.hass.loop.call_soon_threadsafe(
                        asyncio.create_task, self._run_discovery()
                    ),
                )
            except Exception:
                _LOGGER.exception(
                    "Failed to register callback during backoff, abandoning scheduling"
                )
                self._discovery_unsub = None

    async def _run_discovery(self):
        """Run discovery."""
        try:
            _LOGGER.debug("Performing discovery")
            await self._perform_discovery()

            # update next discovery time
            self._next_discovery = datetime.now() + timedelta(
                seconds=self.current_interval
            )

            # adjust interval
            await self._adjust_interval()

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Discovery failed: %s", e)
            # wait 60 seconds before retrying
            self._next_discovery = datetime.now() + timedelta(seconds=60)
        finally:
            # reschedule next discovery
            await self._reschedule()

    async def schedule_immediate_discovery(self, force: bool = False):
        """Immediate discovery."""
        if force:
            _LOGGER.info("Forcing immediate discovery")
            self.hass.async_create_task(self._run_discovery())
        else:
            _LOGGER.debug("Requesting immediate discovery")
            immediate = datetime.now() + timedelta(milliseconds=100)
            if not self._next_discovery or immediate < self._next_discovery:
                self._next_discovery = immediate
                await self._reschedule()

    async def postpone_discovery(self, delay_seconds: int = 300):
        """Postpone discovery."""

        _LOGGER.debug("postpone_discovery")

        new_time = datetime.now() + timedelta(seconds=delay_seconds)

        if not self._next_discovery or new_time > self._next_discovery:
            self._next_discovery = new_time
            _LOGGER.debug("Discovery postponed to: %s", self._next_discovery)
            await self._reschedule()
            return True
        return False

    async def _perform_discovery(self):
        """Perform device discovery."""

        # Record start time
        start_time = datetime.now()

        try:
            discovered_devices = await self._discover_all_devices()

            if discovered_devices:
                async_dispatcher_send(
                    self.hass, SIGNAL_DEVICE_DISCOVERED, discovered_devices
                )

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Device discovery failed: %s", e)

        # Record execution time
        duration = (datetime.now() - start_time).total_seconds()
        _LOGGER.debug("Device discovery completed, took %.2f seconds", duration)

    async def _discover_all_devices(self) -> list[dict]:
        """Discover all devices."""

        results = await self._discover_private_devices()

        flat_results = []
        for r in results:
            if isinstance(r, list):
                flat_results.extend(r)
            else:
                flat_results.append(r)

        discovered = []
        for result in flat_results:
            if not isinstance(result, dict):
                continue
            udn = result.get("UDN")
            if udn:
                discovered.append(result)

        return discovered

    async def _discover_private_devices(self) -> list[dict]:
        """Put blocking scans in executor, then parse responses concurrently."""
        discovered_devices: list[dict] = []
        seen_keys = set()  # Set for deduplication
        lock = asyncio.Lock()  # Lock to protect shared resources

        # 1) Execute synchronous scan in thread pool to avoid blocking event loop
        try:
            # Use Home Assistant recommended executor (will use HA thread pool)
            raw_responses: list[
                tuple[str, tuple[str, int]]
            ] = await self.hass.async_add_executor_job(_scan_speaker_sync)
        except Exception:
            _LOGGER.exception("Private protocol scan (thread) failed")
            return discovered_devices

        if not raw_responses:
            return discovered_devices

        # 2) Concurrently parse responses in event loop (parse_ssdp_response / parse_local_url are both async)
        sem = asyncio.Semaphore(
            8
        )  # Limit concurrency to avoid initiating too many network requests at once

        session = async_get_clientsession(self.hass)

        async def _parse_one(response_text: str, addr: tuple[str, int]):
            async with sem:
                try:
                    dlna_info = await parse_ssdp_response(response_text, addr)
                    location = dlna_info.get("location", "")
                    device_info = await parse_local_url(session, location)
                    if not device_info:
                        return
                    device_key = device_info.get("UDN")

                    if not device_key:
                        return

                    async with lock:
                        # Double check to avoid duplicates
                        if device_key in seen_keys:
                            return

                        seen_keys.add(device_key)
                        device_info["key"] = device_key
                        device_info["ip_addr"] = addr[0]
                        discovered_devices.append(device_info)

                except Exception:
                    _LOGGER.exception("Failed to parse single SSDP response")

        # Create parsing tasks and wait for completion
        tasks = [
            asyncio.create_task(_parse_one(text, addr)) for text, addr in raw_responses
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return discovered_devices

    async def _adjust_interval(self):
        """Dynamically adjust discovery interval."""

        online_count = 0
        offline_count = 0

        try:
            online_count = len(
                [
                    d
                    for d in self.device_manager.device_data_registry._device_data.values()  # noqa: SLF001
                    if d.get("device_dict", {}).get("connection_status")
                    == ConnectionStatus.ONLINE.value
                ]
            )
            offline_count = len(
                [
                    d
                    for d in self.device_manager.device_data_registry._device_data.values()  # noqa: SLF001
                    if d.get("device_dict", {}).get("connection_status")
                    == ConnectionStatus.OFFLINE.value
                ]
            )
        except Exception:
            _LOGGER.exception(
                "Error in calculating online/offline device count during discovery interval adjustment"
            )

        _LOGGER.debug("Current online device count: %d", online_count)
        _LOGGER.debug("Current offline device count: %d", offline_count)

        total_count = online_count + offline_count
        if total_count > 0:
            offline_ratio = offline_count / total_count

            if offline_ratio > 0.8:  # 80% above offline
                self.current_interval = min(
                    self.current_interval * 1.3, self.max_interval
                )
            elif offline_ratio > 0.5:  # 50% above offline
                self.current_interval = min(
                    self.current_interval * 1.1, self.max_interval
                )
            elif offline_ratio == 0:  # all offline
                self.current_interval = max(
                    self.current_interval * 0.9, self.min_interval
                )
            else:  # Few offline, maintain or fine-tune
                self.current_interval = max(
                    self.current_interval * 0.95, self.min_interval
                )

                _LOGGER.debug(
                    "Discovery interval adjusted to %d seconds", self.current_interval
                )


def _scan_speaker_sync() -> list[tuple[str, tuple[str, int]]]:
    """Perform synchronous SSDP M-SEARCH to discover devices."""
    discovered_raw = []
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(SOCKET_TIMEOUT)

        msearch_message = (
            b"M-SEARCH * HTTP/1.1\r\n"
            b"HOST: 239.255.255.250:1900\r\n"
            b'MAN: "ssdp:discover"\r\n'
            b"MX: 3\r\n"
            b"ST: ssdp:wiimudevice\r\n"
            b"USER-AGENT: iOS UPnP/1.1\r\n"
            b"\r\n"
        )

        for _ in range(SEND_REPEAT):
            try:
                sock.sendto(msearch_message, MCAST_ADDR)
            except Exception:  # noqa: BLE001
                # If sending fails, break out of send loop but still try to receive packets that may have arrived
                break

        start = time.time()
        while time.time() - start < SCAN_TOTAL_TIMEOUT:
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode("utf-8", errors="ignore")
                discovered_raw.append((text, addr))
            except TimeoutError:
                # Expected behavior, continue until total time is reached
                continue
            except Exception:  # noqa: BLE001
                # If there are other socket errors, record and break (or continue, depending on requirements)
                break

    finally:
        if sock is not None:
            with contextlib.suppress(Exception):
                sock.close()

    return discovered_raw


async def parse_local_url(session: aiohttp.ClientSession, url: str):
    """Fetch and parse a UPnP device description XML."""
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            xml_content = await response.text()

            root = ET.fromstring(xml_content)

            ns = {
                "device": "urn:schemas-upnp-org:device-1-0",
                "dlna": "urn:schemas-dlna-org:device-1-0",
            }

            device = root.find(".//device:device", ns)
            if device is not None:
                return {
                    "manufacturer": device.findtext("device:manufacturer", "", ns),
                    "friendly_name": device.findtext("device:friendlyName", "", ns),
                    "model_name": device.findtext("device:modelName", "", ns),
                    "UDN": device.findtext("device:UDN", "", ns),
                }
            return None
    except Exception as e:  # noqa: BLE001
        _LOGGER.debug("Error parsing DLNA description: %s", e)
        return None


async def parse_ssdp_response(response_text, addr):
    """Parse an SSDP response into a device info dictionary."""
    device_info = {"ip": addr[0], "port": addr[1], "raw_response": response_text}

    lines = response_text.split("\r\n")
    for line in lines:
        if ":" in line:
            try:
                key, value = line.split(":", 1)
                key = key.strip().lower()  # Header keys are case-insensitive
                value = value.strip()
                if key in {
                    "server",
                    "location",
                    "st",
                    "usn",
                    "cache-control",
                    "ext",
                    "date",
                }:
                    device_info[key] = value
                elif key.startswith("http/"):  # Status line
                    device_info["connection_status"] = value
            except Exception:  # noqa: BLE001
                continue
    return device_info
