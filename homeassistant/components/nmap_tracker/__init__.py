"""The Nmap Tracker integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from getmac import get_mac_address
from nmap import PortScanner, PortScannerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    CONF_HOME_INTERVAL,
    CONF_OPTIONS,
    DOMAIN,
    NMAP_TRACKED_DEVICES,
    PLATFORMS,
    TRACKER_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nmap Tracker from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    devices = domain_data.setdefault(NMAP_TRACKED_DEVICES, NmapTrackedDevices())
    scanner = domain_data[entry.entry_id] = NmapDeviceScanner(hass, entry, devices)
    scanner.async_setup()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@dataclass
class NmapDevice:
    """Class for keeping track of an nmap tracked device."""

    mac_address: str
    hostname: str
    ip_address: str
    last_update: datetime.datetime


class NmapTrackedDevices:
    """Storage class for platform global data."""

    def __init__(self) -> None:
        """Initialize the data."""
        self.tracked: dict = {}


class NmapDeviceScanner:
    """This class scans for devices using nmap."""

    def __init__(self, hass, entry, devices):
        """Initialize the scanner."""
        self._hass = hass
        self._entry = entry
        self._scan_lock = None
        self._entry_id = entry.entry_id
        self.devices = devices

        config = entry.options
        self.last_results = []
        self.hosts = cv.ensure_list(config[CONF_HOSTS])
        self.exclude = cv.ensure_list(config[CONF_EXCLUDE])
        minutes = cv.positive_int(config[CONF_HOME_INTERVAL])
        self._options = config[CONF_OPTIONS]
        self.home_interval = timedelta(minutes=minutes)

    @callback
    def async_setup(self):
        """Set up the tracker."""
        self._scan_lock = asyncio.Lock()
        self.scanner = PortScanner()
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._start_scanner
        )

    def _start_scanner(self, *_):
        """Start the scanner."""
        self._entry.async_on_unload(
            async_track_time_interval(
                self._hass,
                self.async_scan_devices,
                timedelta(seconds=TRACKER_SCAN_INTERVAL),
            )
        )
        self._hass.async_create_task(self.async_scan_devices())

    @property
    def signal_device_new(self) -> str:
        """Signal specific per nmap tracker entry to signal new device."""
        return f"{DOMAIN}-device-new-{self._entry_id}"

    @property
    def signal_device_update(self, formatted_mac) -> str:
        """Signal specific per nmap tracker entry to signal updates in device."""
        return f"{DOMAIN}-device-update-{formatted_mac}"

    def _build_options_from_last_results(self):
        """Build the command line and strip out last results that do not need to be updated."""
        options = self._options
        if self.home_interval:
            boundary = dt_util.now() - self.home_interval
            last_results = [
                device for device in self.last_results if device.last_update > boundary
            ]
            if last_results:
                exclude_hosts = self.exclude + [
                    device.ip_address for device in last_results
                ]
            else:
                exclude_hosts = self.exclude
        else:
            last_results = []
            exclude_hosts = self.exclude
        if exclude_hosts:
            options += f" --exclude {','.join(exclude_hosts)}"
        return options, last_results

    async def async_scan_devices(self, *_):
        """Scan devices and dispatch."""
        if self._scan_lock.locked():
            _LOGGER.warning(
                "Nmap scanning is taking longer than the scheduled interval: %s",
                TRACKER_SCAN_INTERVAL,
            )
            return

        async with self._scan_lock:
            try:
                (
                    online_devices,
                    offline_devices,
                ) = await self._hass.async_add_executor_job(self._run_nmap_scan)
            except PortScannerError as ex:
                _LOGGER.error("nmap scanning failed: %s", ex)
                return

            for device in online_devices:
                async_dispatcher_send(
                    self._hass, self.signal_device_update(device.mac_address), True
                )
                if device.mac_address not in self.devices.tracked:
                    async_dispatcher_send(
                        self._hass, self.signal_device_new, device.mac_address
                    )

            for device in self.devices.tracked.values():
                if device.ip_address in offline_devices:
                    async_dispatcher_send(
                        self.hass, self.signal_device_update(device.mac_address), False
                    )

    def _run_nmap_scan(self):
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        options, last_results = self._build_options_from_last_results()
        _LOGGER.debug("Scanning %s with args: %s", self.hosts, options)
        offline_devices = set()
        result = self.scanner.scan(hosts=" ".join(self.hosts), arguments=options)

        now = dt_util.now()
        for ipv4, info in result["scan"].items():
            if info["status"]["state"] != "up":
                offline_devices.add(ipv4)
                continue
            name = info["hostnames"][0]["name"] if info["hostnames"] else ipv4
            # Mac address only returned if nmap ran as root
            mac = info["addresses"].get("mac") or get_mac_address(ip=ipv4)
            if mac is None:
                _LOGGER.info("No MAC address found for %s", ipv4)
                continue
            formatted_mac = format_mac(mac)

            device = NmapDevice(formatted_mac, name, ipv4, now)
            last_results.append(device)

        _LOGGER.debug("nmap scan successful")
        self.last_results = last_results
        return last_results, offline_devices
