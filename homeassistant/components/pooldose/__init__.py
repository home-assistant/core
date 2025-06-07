"""The Seko Pooldose integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT, SOFTWARE_VERSION
from .coordinator import PooldoseCoordinator
from .pooldose_api import PooldoseAPIClient

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]

"""Configure the Seko Pooldose entry."""


async def async_update_device_info(host: str) -> dict[str, str | None]:
    """Fetch latest device info from all relevant endpoints."""
    device_info: dict[str, str | None] = {}

    headers = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        # Station Info
        try:
            url = f"http://{host}/api/v1/network/wifi/getStation"
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.post(url, headers=headers, timeout=timeout) as resp:
                pass
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            # server always returns bad result due to a bug, however, result can be parsed...
            text = str(err)
            text = text.replace("\\\\n", "").replace("\\\\t", "")
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                data = json.loads(text[json_start:json_end])
                device_info["SSID"] = data.get("SSID")
                device_info["MAC"] = data.get("MAC")
                device_info["IP"] = data.get("IP")

        await asyncio.sleep(1)
        # Network Info
        try:
            url = f"http://{host}/api/v1/network/info/getInfo"
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.post(url, headers=headers, timeout=timeout) as resp:
                data = await resp.json()
                device_info["SYSTEMNAME"] = data.get("SYSTEMNAME")
                device_info["OWNERID"] = data.get("OWNERID")
                device_info["GROUPNAME"] = data.get("GROUPNAME")
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to fetch device info from %s: %s", url, err)

        await asyncio.sleep(1)
        # Access Point Info
        try:
            url = f"http://{host}/api/v1/network/wifi/getAccessPoint"
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.post(url, headers=headers, timeout=timeout) as resp:
                text = await resp.text()
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                if json_start != -1 and json_end != -1:
                    data = json.loads(text[json_start:json_end])
                    device_info["AP_SSID"] = data.get("SSID")
                    device_info["AP_KEY"] = data.get("KEY")
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to fetch device info from %s: %s", url, err)

        # InfoRelease
        try:
            url = f"http://{host}/api/v1/infoRelease"
            payload = {"SOFTWAREVERSION": SOFTWARE_VERSION}
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.post(
                url, json=payload, headers=headers, timeout=timeout
            ) as resp:
                data = await resp.json()
                device_info["APIVERSION_GATEWAY"] = data.get("APIVERSION_GATEWAY")
                device_info["SERIAL_NUMBER"] = data.get("SERIAL_NUMBER")
                device_info["SOFTWAREVERSION_GATEWAY"] = data.get(
                    "SOFTWAREVERSION_GATEWAY"
                )
                device_info["FIRMWARERELEASE_DEVICE"] = data.get(
                    "FIRMWARERELEASE_DEVICE"
                )
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to fetch device info from %s: %s", url, err)

        # Model Info from /api/v1/debug/config
        try:
            url = f"http://{host}/api/v1/debug/config"
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.get(url, timeout=timeout) as resp:
                data = await resp.json()
                if (device := data.get("DEVICES")[0]) is not None:
                    device_info["NAME"] = device.get("NAME")
                    device_info["PRODUCT_CODE"] = device.get("PRODUCT_CODE")
        except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to fetch model info from %s: %s", url, err)

    return device_info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Seko Pooldose from a config entry."""
    config = entry.data
    host = config["host"]
    serial = config["serialnumber"]
    scan_interval = config.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    timeout = config.get("timeout", DEFAULT_TIMEOUT)

    api = PooldoseAPIClient(
        host=host,
        serial_number=serial,
        timeout=timeout,
        scan_interval=scan_interval,
    )

    coordinator = PooldoseCoordinator(hass, api, timedelta(seconds=scan_interval))
    await coordinator.async_config_entry_first_refresh()

    # Update device info on every reload
    device_info = await async_update_device_info(host)

    hass.data.setdefault("pooldose", {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Seko Pooldose entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
