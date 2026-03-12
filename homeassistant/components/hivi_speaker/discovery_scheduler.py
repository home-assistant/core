from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, List, Tuple
import xml.etree.ElementTree as ET
import socket
import aiohttp
import time

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from .const import DOMAIN, SIGNAL_DEVICE_DISCOVERED
from .device import SyncGroupStatus, ConnectionStatus, HIVIDevice
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

SCAN_TOTAL_TIMEOUT = 5.0  # seconds
SOCKET_TIMEOUT = 1.0  # seconds
SEND_REPEAT = 3
MCAST_ADDR = ("239.255.255.250", 1900)


class HIVIDiscoveryScheduler:
    """Intelligent discovery scheduler"""

    def __init__(self, hass, config_entry, device_manager, base_interval: int = 300):
        self.hass = hass
        self.config_entry = config_entry
        self.device_manager = device_manager
        self.base_interval = base_interval  # 5-minute base interval

        # Dynamic adjustment
        self.current_interval = base_interval
        self.min_interval = 120  # Minimum 10 seconds
        self.max_interval = 600  # Maximum 10 minutes

        # Status flags
        self._discovery_task: Optional[asyncio.Task] = None
        self._discovery_running = False
        self._next_discovery: Optional[datetime] = None
        self._scheduled_calls: Set[str] = set()  # Called device IDs

        # Operation delay tracking
        self._operation_delays: Dict[
            str, datetime
        ] = {}  # speaker_device_id -> operation time
        # Immediate discovery flag
        self._immediate_discovery_requested = False
        self._discovery_lock = asyncio.Lock()

        # Stop discovery
        self._discovery_unsub = None

    async def async_start(self):
        """Start scheduler"""

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
            """async_call_later callback: may execute in a non-event-loop thread,
            so we need to use loop.call_soon_threadsafe to send the task creation operation back to the event loop thread for execution."""
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
        """Run discovery"""
        try:
            _LOGGER.debug("Performing discovery")
            await self._perform_discovery()

            # update next discovery time
            self._next_discovery = datetime.now() + timedelta(
                seconds=self.current_interval
            )

            # adjust interval
            await self._adjust_interval()

        except Exception as e:
            _LOGGER.error("Discovery failed: %s", e)
            # wait 60 seconds before retrying
            self._next_discovery = datetime.now() + timedelta(seconds=60)
        finally:
            # reschedule next discovery
            await self._reschedule()

    async def schedule_immediate_discovery(self, force: bool = False):
        """Immediate discovery"""
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
        """Postpone discovery"""

        _LOGGER.debug("postpone_discovery")

        new_time = datetime.now() + timedelta(seconds=delay_seconds)

        if not self._next_discovery or new_time > self._next_discovery:
            self._next_discovery = new_time
            _LOGGER.debug("Discovery postponed to: %s", self._next_discovery)
            await self._reschedule()
            return True
        return False

    async def _perform_discovery(self):
        """Perform device discovery"""
        # _LOGGER.debug("Starting device discovery cycle")

        # Record start time
        start_time = datetime.now()

        try:
            discovered_devices = await self._discover_all_devices()

            if discovered_devices:
                async_dispatcher_send(
                    self.hass, SIGNAL_DEVICE_DISCOVERED, discovered_devices
                )

        except Exception as e:
            _LOGGER.error("Device discovery failed: %s", e)

        # Record execution time
        duration = (datetime.now() - start_time).total_seconds()
        _LOGGER.debug("Device discovery completed, took %.2f seconds", duration)

    async def _discover_all_devices(self) -> List[Dict]:
        """Discover all devices"""

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

    async def _discover_private_devices(self) -> List[Dict]:
        """
        Put blocking scans in executor, then concurrently parse each response in event loop, finally return device dictionary with device_key as key.
        """
        discovered_devices: List[Dict] = []
        seen_keys = set()  # Set for deduplication
        lock = asyncio.Lock()  # Lock to protect shared resources

        # 1) Execute synchronous scan in thread pool to avoid blocking event loop
        try:
            # Use Home Assistant recommended executor (will use HA thread pool)
            raw_responses: List[
                Tuple[str, Tuple[str, int]]
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

        async def _parse_one(response_text: str, addr: Tuple[str, int]):
            async with sem:
                try:
                    dlna_info = await parse_ssdp_response(response_text, addr)
                    location = dlna_info.get("location", "")
                    device_info = await parse_local_url(location)
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

    # Compare discovered and existing devices to find currently online, offline, and newly discovered ones
    async def compare_dict(self, Dict1: Dict[str, HIVIDevice], Dict2: Dict[str, Dict]):
        online_items = {}
        offline_items = {}
        newdevices_items = {}
        for key, value in Dict1.items():
            if key in Dict2:
                online_items[key] = value
            else:
                offline_items[key] = value
        for key, value in Dict2.items():
            if key not in Dict1:
                newdevices_items[key] = value
        return online_items, offline_items, newdevices_items

    async def _adjust_interval(self):
        """Dynamically adjust discovery interval"""

        online_count = 0
        offline_count = 0

        try:
            online_count = len(
                [
                    d
                    for d in self.device_manager.device_data_registry._device_data.values()
                    if d.get("device_dict").get("connection_status")
                    == ConnectionStatus.ONLINE
                ]
            )
            offline_count = len(
                [
                    d
                    for d in self.device_manager.device_data_registry._device_data.values()
                    if d.get("device_dict").get("connection_status")
                    == ConnectionStatus.OFFLINE
                ]
            )
            # offline_count = len(self._offline_devices)
        except Exception as e:
            _LOGGER.exception(
                f"error in calculating online/offline device count during discovery interval adjustment {e}"
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


def _scan_speaker_sync() -> List[Tuple[str, Tuple[str, int]]]:
    """
    scan_speaker_sync performs synchronous SSDP M-SEARCH to discover devices.
    """
    discovered_raw = []
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(SOCKET_TIMEOUT)

        msearch_message = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 3\r\n"
            f"ST: ssdp:wiimudevice\r\n"
            "USER-AGENT: iOS UPnP/1.1\r\n"
            "\r\n"
        ).encode("utf-8")

        for _ in range(SEND_REPEAT):
            try:
                sock.sendto(msearch_message, MCAST_ADDR)
            except Exception:
                # If sending fails, break out of send loop but still try to receive packets that may have arrived
                break

        start = time.time()
        while time.time() - start < SCAN_TOTAL_TIMEOUT:
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode("utf-8", errors="ignore")
                discovered_raw.append((text, addr))
            except socket.timeout:
                # Expected behavior, continue until total time is reached
                continue
            except Exception:
                # If there are other socket errors, record and break (or continue, depending on requirements)
                break

    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    return discovered_raw


async def parse_local_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                response.raise_for_status()
                xml_content = await response.text()

                root = ET.fromstring(xml_content)

                ns = {
                    "device": "urn:schemas-upnp-org:device-1-0",
                    "dlna": "urn:schemas-dlna-org:device-1-0",
                }

                device = root.find(".//device:device", ns)
                if device is not None:
                    result = {
                        "manufacturer": device.findtext("device:manufacturer", "", ns),
                        "friendly_name": device.findtext("device:friendlyName", "", ns),
                        "model_name": device.findtext("device:modelName", "", ns),
                        "UDN": device.findtext("device:UDN", "", ns),
                    }
                    return result
                return None
    except Exception as e:
        _LOGGER.debug("Error parsing DLNA description: %s", e)
        return None


async def parse_ssdp_response(response_text, addr):
    device_info = {"ip": addr[0], "port": addr[1], "raw_response": response_text}

    lines = response_text.split("\r\n")
    for line in lines:
        if ":" in line:
            try:
                key, value = line.split(":", 1)
                key = key.strip().lower()  # Header keys are case-insensitive
                value = value.strip()
                # _LOGGER.debug("Parsed SSDP header: %s: %s", key, value)
                if key in [
                    "server",
                    "location",
                    "st",
                    "usn",
                    "cache-control",
                    "ext",
                    "date",
                ]:
                    device_info[key] = value
                elif key.startswith("http/"):  # Status line
                    device_info["connection_status"] = value
            except:
                # skip this line
                continue
    return device_info
