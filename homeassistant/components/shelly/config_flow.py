"""Config flow for Shelly integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Final, cast

import aiohttp
import aioshelly
import async_timeout
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import AIOSHELLY_DEVICE_TIMEOUT_SEC, DOMAIN
from .utils import get_coap_context, get_device_sleep_period

_LOGGER: Final = logging.getLogger(__name__)

HOST_SCHEMA: Final = vol.Schema({vol.Required(CONF_HOST): str})

HTTP_CONNECT_ERRORS: Final = (asyncio.TimeoutError, aiohttp.ClientError)


async def validate_input(
    hass: core.HomeAssistant, host: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    options = aioshelly.ConnectionOptions(
        host, data.get(CONF_USERNAME), data.get(CONF_PASSWORD)
    )
    coap_context = await get_coap_context(hass)

    async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
        device = await aioshelly.Device.create(
            aiohttp_client.async_get_clientsession(hass),
            coap_context,
            options,
        )

    device.shutdown()

    # Return info that you want to store in the config entry.
    return {
        "title": device.settings["name"],
        "hostname": device.settings["device"]["hostname"],
        "sleep_period": get_device_sleep_period(device.settings),
        "model": device.settings["device"]["type"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shelly."""

    VERSION = 1

    host: str = ""
    info: dict[str, Any] = {}
    device_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST]
            try:
                info = await self._async_get_info(host)
            except HTTP_CONNECT_ERRORS:
                errors["base"] = "cannot_connect"
            except aioshelly.FirmwareUnsupported:
                return self.async_abort(reason="unsupported_firmware")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["mac"])
                self._abort_if_unique_id_configured({CONF_HOST: host})
                self.host = host
                if info["auth"]:
                    return await self.async_step_credentials()

                try:
                    device_info = await validate_input(self.hass, self.host, {})
                except HTTP_CONNECT_ERRORS:
                    errors["base"] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=device_info["title"] or device_info["hostname"],
                        data={
                            **user_input,
                            "sleep_period": device_info["sleep_period"],
                            "model": device_info["model"],
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=HOST_SCHEMA, errors=errors
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_info = await validate_input(self.hass, self.host, user_input)
            except aiohttp.ClientResponseError as error:
                if error.status == HTTP_UNAUTHORIZED:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except HTTP_CONNECT_ERRORS:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=device_info["title"] or device_info["hostname"],
                    data={
                        **user_input,
                        CONF_HOST: self.host,
                        "sleep_period": device_info["sleep_period"],
                        "model": device_info["model"],
                    },
                )
        else:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME)): str,
                vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)): str,
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        try:
            self.info = info = await self._async_get_info(discovery_info["host"])
        except HTTP_CONNECT_ERRORS:
            return self.async_abort(reason="cannot_connect")
        except aioshelly.FirmwareUnsupported:
            return self.async_abort(reason="unsupported_firmware")

        await self.async_set_unique_id(info["mac"])
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info["host"]})
        self.host = discovery_info["host"]

        self.context["title_placeholders"] = {
            "name": discovery_info.get("name", "").split(".")[0]
        }

        if info["auth"]:
            return await self.async_step_credentials()

        try:
            self.device_info = await validate_input(self.hass, self.host, {})
        except HTTP_CONNECT_ERRORS:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title=self.device_info["title"] or self.device_info["hostname"],
                data={
                    "host": self.host,
                    "sleep_period": self.device_info["sleep_period"],
                    "model": self.device_info["model"],
                },
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "model": aioshelly.MODEL_NAMES.get(
                    self.info["type"], self.info["type"]
                ),
                "host": self.host,
            },
            errors=errors,
        )

    async def _async_get_info(self, host: str) -> dict[str, Any]:
        """Get info from shelly device."""
        async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
            return cast(
                Dict[str, Any],
                await aioshelly.get_info(
                    aiohttp_client.async_get_clientsession(self.hass),
                    host,
                ),
            )
