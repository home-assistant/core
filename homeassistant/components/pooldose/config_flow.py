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

from .const import CONF_SERIALNUMBER, DEFAULT_HOST, DOMAIN, SOFTWARE_VERSION

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
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
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
                entry_data = {CONF_HOST: host, CONF_SERIALNUMBER: serial_number}
                return self.async_create_entry(
                    title="PoolDose - S/N " + serial_number, data=entry_data
                )

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
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            _LOGGER.error("Failed to fetch device info from %s: %s", url, err)
        return None


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
