"""API client for Wibeee energy monitor integration with Home Assistant."""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import timedelta
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class WibeeeDeviceInfo:
    """Represents Wibeee device information."""

    def __init__(
        self,
        wibeee_id: str,
        mac_addr: str,
        model: str,
        firmware_version: str,
        ip_addr: str,
    ) -> None:
        """Initialize device info."""
        self.wibeee_id = wibeee_id
        self.mac_addr = mac_addr
        self.model = model
        self.firmware_version = firmware_version
        self.ip_addr = ip_addr

    @property
    def mac_addr_formatted(self) -> str:
        """Return MAC address without colons, lowercase."""
        return self.mac_addr.replace(":", "").lower()

    @property
    def mac_addr_short(self) -> str:
        """Return last 6 chars of MAC address, uppercase."""
        return self.mac_addr_formatted[-6:].upper()


class WibeeeAPI:
    """Async API client for Wibeee energy monitors.

    Uses aiohttp (the HA-preferred HTTP client) for all communication.
    Provides methods to fetch device info, status, and sensor values.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 80,
        timeout: timedelta = timedelta(seconds=10),
    ) -> None:
        """Initialize the API client."""
        self.session = session
        self.host = host
        self.port = port
        self.timeout = aiohttp.ClientTimeout(total=timeout.total_seconds())

    @property
    def base_url(self) -> str:
        """Return the base URL for the device."""
        return f"http://{self.host}:{self.port}"

    async def async_fetch_url(self, url: str, retries: int = 0) -> str | None:
        """Fetch a URL with optional retries, returning text content."""
        for attempt in range(retries + 1):
            try:
                async with self.session.get(url, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    _LOGGER.warning(
                        "HTTP %d from %s (attempt %d/%d)",
                        resp.status,
                        url,
                        attempt + 1,
                        retries + 1,
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                _LOGGER.debug(
                    "Error fetching %s (attempt %d/%d): %s",
                    url,
                    attempt + 1,
                    retries + 1,
                    exc,
                )

            if attempt < retries:
                wait = min(2 ** (attempt + 1) * 0.1, 5.0)
                await asyncio.sleep(wait)

        _LOGGER.error("Failed to fetch %s after %d attempts", url, retries + 1)
        return None

    async def async_fetch_status(self, retries: int = 2) -> dict[str, Any] | None:
        """Fetch status.xml and return parsed sensor data.

        Returns a dict like:
        {
            "fase1_vrms": "230.5",
            "fase1_irms": "2.3",
            "fase2_vrms": "231.0",
            ...
            "model": "WBB",
            "webversion": "4.4.199",
        }
        """
        url = f"{self.base_url}/en/status.xml"
        text = await self.async_fetch_url(url, retries=retries)
        if not text:
            return None

        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            _LOGGER.error("Error parsing status XML: %s", exc)
            return None

        if root.tag != "response":
            return None

        return {child.tag: child.text or "" for child in root}

    async def async_fetch_device_info(
        self, retries: int = 3
    ) -> WibeeeDeviceInfo | None:
        """Fetch device information (model, MAC, firmware, etc.).

        Tries to get info from status.xml first. Falls back to
        devices.xml + values.xml and web scraping if needed.
        """
        # Try status.xml first - it often contains model and version
        status = await self.async_fetch_status(retries=retries)

        model: str | None = None
        firmware_version: str | None = None

        if status:
            model = status.get("model")
            firmware_version = status.get("webversion")

        # Get device name/id from devices.xml
        wibeee_id = await self._fetch_device_id(retries=retries)
        if not wibeee_id:
            wibeee_id = "WIBEEE"

        # Get MAC address from values.xml
        mac_addr = await self._fetch_mac_address(wibeee_id, retries=retries)

        # If model is still unknown, try web scraping
        if not model:
            model = await self._fetch_model_from_web(retries=retries)

        # If firmware version is still unknown, try values.xml
        if not firmware_version:
            firmware_version = await self._fetch_value(
                wibeee_id, "softVersion", retries=retries
            )

        if not mac_addr:
            _LOGGER.error("Could not determine MAC address for %s", self.host)
            return None

        return WibeeeDeviceInfo(
            wibeee_id=wibeee_id,
            mac_addr=mac_addr,
            model=model or "Unknown",
            firmware_version=firmware_version or "Unknown",
            ip_addr=self.host,
        )

    async def _fetch_device_id(self, retries: int = 2) -> str | None:
        """Fetch the device ID from devices.xml."""
        url = f"{self.base_url}/services/user/devices.xml"
        text = await self.async_fetch_url(url, retries=retries)
        if not text:
            return None

        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            _LOGGER.debug("Error parsing devices.xml: %s", exc)
            return None

        if root.tag == "devices":
            return root.findtext("id")
        return None

    async def _fetch_mac_address(self, wibeee_id: str, retries: int = 2) -> str | None:
        """Fetch MAC address from values.xml."""
        mac = await self._fetch_value(wibeee_id, "macAddr", retries=retries)
        if mac:
            return mac.replace(":", "").lower()
        return None

    async def _fetch_value(
        self, wibeee_id: str, var_name: str, retries: int = 2
    ) -> str | None:
        """Fetch a single variable value from the device."""
        url = f"{self.base_url}/services/user/values.xml?var={wibeee_id}.{var_name}"
        text = await self.async_fetch_url(url, retries=retries)
        if not text:
            return None

        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            _LOGGER.debug("Error parsing values.xml for %s: %s", var_name, exc)
            return None

        for var in root.findall("variable"):
            if var.findtext("id") == var_name:
                return var.findtext("value")
        return None

    async def _fetch_model_from_web(self, retries: int = 1) -> str | None:
        """Try to determine the model by scraping the web interface.

        Uses the device's default credentials (user/user) to access
        the web interface. This is a fallback when model info is not
        available in status.xml.
        """
        # Login first with device default credentials
        login_url = f"{self.base_url}/en/loginRedirect.html?user=user&pwd=user"
        await self.async_fetch_url(login_url, retries=0)

        # Then get the index page which contains the model in JavaScript
        index_url = f"{self.base_url}/en/index.html"
        text = await self.async_fetch_url(index_url, retries=retries)
        if not text:
            return None

        search = 'var model = "'
        start = text.find(search)
        if start != -1:
            end = text.find('"', start + len(search))
            if end != -1:
                return text[start + len(search) : end]
        return None

    async def async_fetch_sensors_data(
        self, retries: int = 2
    ) -> dict[str, dict[str, str]] | None:
        """Fetch and parse status.xml, returning organized sensor data.

        Returns a dict organized by phase:
        {
            "fase1": {"vrms": "230.5", "irms": "2.3", ...},
            "fase2": {"vrms": "231.0", ...},
            "fase3": {"vrms": "230.8", ...},
            "fase4": {"vrms": "230.8", ...},  # total/aggregate
        }
        """
        status = await self.async_fetch_status(retries=retries)
        if not status:
            return None

        phases: dict[str, dict[str, str]] = {}
        for key, value in status.items():
            if key.startswith("fase"):
                # Keys are like "fase1_vrms", "fase2_irms", etc.
                parts = key.split("_", 1)
                if len(parts) == 2:
                    phase = parts[0]  # "fase1", "fase2", etc.
                    sensor_key = parts[1]  # "vrms", "irms", etc.
                    if phase not in phases:
                        phases[phase] = {}
                    phases[phase][sensor_key] = value

        return phases if phases else None

    async def async_reboot(self) -> bool:
        """Reboot the device via web interface."""
        url = f"{self.base_url}/config_value?reboot=1"
        result = await self.async_fetch_url(url, retries=0)
        return result is not None

    async def async_reset_energy(self) -> bool:
        """Reset energy counters via web interface."""
        url = f"{self.base_url}/resetEnergy?resetEn=1"
        result = await self.async_fetch_url(url, retries=0)
        return result is not None

    async def async_check_connection(self) -> bool:
        """Check if the device is reachable."""
        url = f"{self.base_url}/en/login.html"
        text = await self.async_fetch_url(url, retries=1)
        if text and "<title>WiBeee</title>" in text:
            return True
        # Some firmware versions use different title
        if text and "WiBeee" in text:
            return True
        return False

    async def async_configure_push_server(
        self, server_ip: str, server_port: int = 8123
    ) -> bool:
        """Configure the WiBeee device to push data to a server.

        This tells the WiBeee to send its periodic data to the specified
        IP and port. Typically the port is HA's HTTP port (8123 by default),
        since the push receiver is registered as an HTTP view within HA.

        The WiBeee firmware expects the port in hexadecimal format.
        For example: 8123 decimal = 1fbb hex, 8080 = 1f90 hex.

        After configuring, a reset is sent so the device applies changes.

        Args:
            server_ip: IP address of the server to push data to.
            server_port: Port number (decimal). Default 8123 (HA port).

        Returns:
            True if configuration was applied successfully.
        """
        # Convert port to hex (4 chars, zero-padded) as the firmware expects
        port_hex = format(server_port, "04x")

        # Configure the server URL and port
        url = (
            f"{self.base_url}/configura_server"
            f"?ipServidor={server_ip}"
            f"&URLServidor={server_ip}"
            f"&portServidor={port_hex}"
        )
        _LOGGER.info(
            "Configuring WiBeee %s to push to %s:%d (port hex: %s)",
            self.host,
            server_ip,
            server_port,
            port_hex,
        )
        result = await self.async_fetch_url(url, retries=2)
        if result is None:
            _LOGGER.error("Failed to configure push server on WiBeee %s", self.host)
            return False

        # Reset the device to apply changes
        reset_url = f"{self.base_url}/config_value?reset=true"
        await self.async_fetch_url(reset_url, retries=1)

        _LOGGER.info(
            "WiBeee %s configured to push to %s:%d - device is restarting",
            self.host,
            server_ip,
            server_port,
        )
        return True

    async def async_get_push_server_config(
        self,
    ) -> dict[str, Any] | None:
        """Read the current push server configuration from the device.

        Returns a dict with 'server_ip' and 'server_port' (decimal),
        or None if not readable.
        """
        wibeee_id = await self._fetch_device_id(retries=1)
        if not wibeee_id:
            wibeee_id = "WIBEEE"

        server_ip = await self._fetch_value(wibeee_id, "serverIP", retries=1)
        server_port_hex = await self._fetch_value(wibeee_id, "serverPort", retries=1)

        if server_ip and server_port_hex:
            try:
                server_port = int(server_port_hex, 16)
            except ValueError:
                server_port = 0
            return {
                "server_ip": server_ip,
                "server_port": server_port,
            }

        return None

    async def async_fetch_device_diagnostics(self) -> dict[str, Any]:
        """Fetch device configuration variables for diagnostics.

        Reads values.xml variables documented by the manufacturer that
        provide insight into the device's configuration and state.
        Sensitive fields (IP, MAC, WiFi credentials) are excluded;
        those are redacted at the diagnostics layer.
        """
        wibeee_id = await self._fetch_device_id(retries=1)
        if not wibeee_id:
            wibeee_id = "WIBEEE"

        diag_vars = [
            "connectionType",
            "phasesSequence",
            "harmonics",
            "softVersion",
            "model",
            "ipType",
            "networkType",
            "spiFlashId",
            "leapThreshold",
            "clampsModel",
            "scale",
            "measuresRefresh",
            "appRefresh",
            "HDataSaveRefresh",
        ]

        result: dict[str, Any] = {}
        for var_name in diag_vars:
            value = await self._fetch_value(wibeee_id, var_name, retries=1)
            if value is not None:
                result[var_name] = value

        # Also fetch status.xml extras (scale, coilStatus, ground, time)
        status = await self.async_fetch_status(retries=1)
        if status:
            for key in ("scale", "coilStatus", "ground", "time"):
                if key in status:
                    result[f"status_{key}"] = status[key]

        return result
