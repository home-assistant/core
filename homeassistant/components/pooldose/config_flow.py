"""Config flow for the Seko Pooldose integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    APIVERSION,
    CONF_SERIALNUMBER,
    DEFAULT_HOST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SOFTWARE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

SCHEMA_DEVICE = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def get_device_info(host: str) -> dict[str, Any] | None:
    """Fetch and validate device info from the Pooldose API."""
    url = f"http://{host}/api/v1/infoRelease"
    payload = {"SOFTWAREVERSION": SOFTWARE_VERSION}
    headers = {"Content-Type": "application/json"}
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, json=payload, headers=headers, timeout=timeout) as resp,
        ):
            return await resp.json()
    except (aiohttp.ClientError, TimeoutError, OSError) as err:
        _LOGGER.error("Failed to fetch device info from %s: %s", url, err)
    return None


def validate_api_version(api_version: str) -> tuple[bool, dict[str, str] | None]:
    """Validate if the API version is supported."""
    if api_version != APIVERSION:
        return False, {
            "api_version_is": api_version,
            "api_version_should": APIVERSION,
        }
    return True, None


class PooldoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seko Pooldose."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        error_placeholders = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                info = await get_device_info(host)
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.error("Failed to fetch device info from %s: %s", host, err)
                errors["base"] = "cannot_connect"
                info = None
            except Exception:
                _LOGGER.exception("Unexpected exception during device info fetch")
                errors["base"] = "unknown"
                info = None
            if not info and "base" not in errors:
                errors["base"] = "cannot_connect"
            elif info:
                api_ver = info["APIVERSION_GATEWAY"]
                valid, placeholders = validate_api_version(api_ver)
                if not valid:
                    errors["base"] = "api_not_supported"
                    error_placeholders = placeholders
                else:
                    serial_number = info["SERIAL_NUMBER"]
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured()
                    entry_data = {CONF_HOST: host, CONF_SERIALNUMBER: serial_number}
                    return self.async_create_entry(
                        title=f"PoolDose {serial_number}", data=entry_data
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA_DEVICE,
            errors=errors,
            description_placeholders=error_placeholders,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler for Pooldose."""
        return PooldoseOptionsFlowHandler(config_entry)


class PooldoseOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle (re-)configuration after initial setup."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize the Pooldose options flow handler."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Options form."""
        errors: dict[str, str] = {}
        error_placeholders = None
        if user_input is not None:
            # Only allow changing scan interval and timeout, not host
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_SCAN_INTERVAL: self.entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
            CONF_TIMEOUT: self.entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]
                    ): cv.positive_int,
                    vol.Required(
                        CONF_TIMEOUT, default=defaults[CONF_TIMEOUT]
                    ): cv.positive_int,
                }
            ),
            errors=errors,
            description_placeholders=error_placeholders,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
