"""Config flow for the Seko Pooldose integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_SERIALNUMBER,
    DEFAULT_HOST,
    DEFAULT_SERIAL_NUMBER,
    DOMAIN,
    SOFTWARE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_SERIALNUMBER, default=DEFAULT_SERIAL_NUMBER): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
        vol.Optional(CONF_TIMEOUT): cv.positive_int,
    }
)


class PooldoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seko Pooldose."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            info = await self._async_get_device_info(host)
            if not info or "SERIAL_NUMBER" not in info:
                errors["base"] = "cannot_connect"
            else:
                serial_number = info["SERIAL_NUMBER"]
                firmware_version = info.get("SOFTWAREVERSION_GATEWAY")
                hardware_version = info.get("FIRMWARERELEASE_DEVICE")
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
                entry_data = {
                    CONF_HOST: host,
                    CONF_SERIALNUMBER: serial_number,
                    "SOFTWAREVERSION_GATEWAY": firmware_version,
                    "FIRMWARECODE_DEVICE": hardware_version,
                }
                # import logging

                # _LOGGER = logging.getLogger(__name__)
                # _LOGGER.error("config flow entry_data %s", entry_data)

                return self.async_create_entry(title=serial_number, data=entry_data)

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_DEVICE, errors=errors
        )

    async def _async_get_device_info(self, host: str) -> dict[str, Any] | None:
        """Fetch device info from the Pooldose API."""
        url = f"http://{host}/api/v1/infoRelease"
        payload = {"SOFTWAREVERSION": SOFTWARE_VERSION}
        headers = {"Content-Type": "application/json"}
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json=payload, headers=headers, timeout=timeout
                ) as resp,
            ):
                if resp.status == 200:
                    return await resp.json()
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.error("Failed to fetch device info from %s: %s", url, err)
        return None

    # async def _async_get_station(self, host: str) -> dict[str, str | None] | None:
    #     """Fetch SSID, MAC, and IP from the Pooldose API."""
    #     url = f"http://{host}/api/v1/network/wifi/getStation"
    #     headers = {
    #         "Content-Type": "application/json",
    #     }
    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             async with session.post(url, headers=headers, timeout=5) as resp:
    #                 text = await resp.text()
    #     except (aiohttp.ClientError, TimeoutError, OSError) as err:
    #         # _LOGGER.error("Failed to fetch device info from %s: %s", url, str(err))
    #         # server always returns a 200 OK status, even on error, proceed...
    #         text = str(err)
    #         # Extract JSON part from the response, even on error status
    #         text = text.replace("\\\\n", "").replace("\\\\t", "")
    #         json_start = text.find("{")
    #         json_end = text.rfind("}") + 1
    #         if json_start != -1 and json_end != -1:
    #             json_str = text[json_start:json_end]
    #             try:
    #                 data = json.loads(json_str)
    #             except Exception as err2:
    #                 _LOGGER.error(
    #                     "Could not parse JSON from SSID response: %s (%s)",
    #                     json_str,
    #                     err2,
    #                 )
    #                 return None
    #             return data
    #         _LOGGER.error(
    #             "Could not extract JSON from SSID response: %s",
    #             text,
    #         )
    #     return None

    # async def _async_get_network_info(self, host: str) -> dict[str, Any] | None:
    #     """Fetch network info (SYSTEMNAME, OWNERID) from the Pooldose API."""
    #     url = f"http://{host}/api/v1/network/info/getInfo"
    #     headers = {"Content-Type": "application/json", "Accept": "application/json"}
    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             async with session.post(url, headers=headers, timeout=5) as resp:
    #                 if resp.status == 200:
    #                     return await resp.json()
    #     except (aiohttp.ClientError, TimeoutError, OSError) as err:
    #         _LOGGER.error("Failed to fetch network info from %s: %s", url, err)
    #     return None

    # async def _async_get_access_point(self, host: str) -> dict[str, str | None] | None:
    #     """Fetch Access Point SSID and KEY from the Pooldose API."""
    #     url = f"http://{host}/api/v1/network/wifi/getAccessPoint"
    #     headers = {
    #         "Content-Type": "application/json",
    #         "Accept": "application/json, text/javascript, */*; q=0.01",
    #         "Cache-Control": "no-cache",
    #         "Connection": "keep-alive",
    #         "Content-Length": "0",
    #         "DNT": "1",
    #         "Pragma": "no-cache",
    #         "X-Requested-With": "XMLHttpRequest",
    #     }
    #     try:
    #         async with aiohttp.ClientSession() as session:
    #             async with session.post(url, headers=headers, timeout=5) as resp:
    #                 text = await resp.text()
    #                 json_start = text.find("{")
    #                 json_end = text.rfind("}") + 1
    #                 if json_start != -1 and json_end != -1:
    #                     json_str = text[json_start:json_end]
    #                     try:
    #                         data = json.loads(json_str)
    #                     except Exception as err:
    #                         _LOGGER.error(
    #                             "Could not parse JSON from AP response: %s (%s)",
    #                             json_str,
    #                             err,
    #                         )
    #                         return None
    #                     return {
    #                         "AP_SSID": data.get("SSID"),
    #                         "AP_KEY": data.get("KEY"),
    #                     }
    #                 _LOGGER.error(
    #                     "Could not extract JSON from AP response: %s",
    #                     text,
    #                 )
    #     except (aiohttp.ClientError, TimeoutError, OSError) as err:
    #         _LOGGER.error("Failed to fetch AP info from %s: %s", url, str(err))
    #     return None


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
