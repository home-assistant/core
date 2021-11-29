"""Config flow for Shelly integration."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import Any, Final

import aiohttp
import aioshelly
from aioshelly.block_device import BlockDevice
from aioshelly.rpc_device import RpcDevice
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import AIOSHELLY_DEVICE_TIMEOUT_SEC, CONF_SLEEP_PERIOD, DOMAIN
from .utils import (
    get_block_device_name,
    get_block_device_sleep_period,
    get_coap_context,
    get_info_auth,
    get_info_gen,
    get_model_name,
    get_rpc_device_name,
)

_LOGGER: Final = logging.getLogger(__name__)

HOST_SCHEMA: Final = vol.Schema({vol.Required(CONF_HOST): str})

HTTP_CONNECT_ERRORS: Final = (asyncio.TimeoutError, aiohttp.ClientError)


async def validate_input(
    hass: HomeAssistant,
    host: str,
    info: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from HOST_SCHEMA with values provided by the user.
    """
    options = aioshelly.common.ConnectionOptions(
        host,
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
    )

    async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
        if get_info_gen(info) == 2:
            rpc_device = await RpcDevice.create(
                aiohttp_client.async_get_clientsession(hass),
                options,
            )
            await rpc_device.shutdown()
            return {
                "title": get_rpc_device_name(rpc_device),
                CONF_SLEEP_PERIOD: 0,
                "model": rpc_device.model,
                "gen": 2,
            }

        # Gen1
        coap_context = await get_coap_context(hass)
        block_device = await BlockDevice.create(
            aiohttp_client.async_get_clientsession(hass),
            coap_context,
            options,
        )
        block_device.shutdown()
        return {
            "title": get_block_device_name(block_device),
            CONF_SLEEP_PERIOD: get_block_device_sleep_period(block_device.settings),
            "model": block_device.model,
            "gen": 1,
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
                self.info = await self._async_get_info(host)
            except HTTP_CONNECT_ERRORS:
                errors["base"] = "cannot_connect"
            except aioshelly.exceptions.FirmwareUnsupported:
                return self.async_abort(reason="unsupported_firmware")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self.info["mac"])
                self._abort_if_unique_id_configured({CONF_HOST: host})
                self.host = host
                if get_info_auth(self.info):
                    return await self.async_step_credentials()

                try:
                    device_info = await validate_input(
                        self.hass, self.host, self.info, {}
                    )
                except HTTP_CONNECT_ERRORS:
                    errors["base"] = "cannot_connect"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=device_info["title"],
                        data={
                            **user_input,
                            CONF_SLEEP_PERIOD: device_info[CONF_SLEEP_PERIOD],
                            "model": device_info["model"],
                            "gen": device_info["gen"],
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
                device_info = await validate_input(
                    self.hass, self.host, self.info, user_input
                )
            except aiohttp.ClientResponseError as error:
                if error.status == HTTPStatus.UNAUTHORIZED:
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
                    title=device_info["title"],
                    data={
                        **user_input,
                        CONF_HOST: self.host,
                        CONF_SLEEP_PERIOD: device_info[CONF_SLEEP_PERIOD],
                        "model": device_info["model"],
                        "gen": device_info["gen"],
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
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info[zeroconf.ATTR_HOST]
        try:
            self.info = await self._async_get_info(host)
        except HTTP_CONNECT_ERRORS:
            return self.async_abort(reason="cannot_connect")
        except aioshelly.exceptions.FirmwareUnsupported:
            return self.async_abort(reason="unsupported_firmware")

        await self.async_set_unique_id(self.info["mac"])
        self._abort_if_unique_id_configured({CONF_HOST: host})
        self.host = host

        self.context["title_placeholders"] = {"name": discovery_info.name.split(".")[0]}

        if get_info_auth(self.info):
            return await self.async_step_credentials()

        try:
            self.device_info = await validate_input(self.hass, self.host, self.info, {})
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
                title=self.device_info["title"],
                data={
                    "host": self.host,
                    CONF_SLEEP_PERIOD: self.device_info[CONF_SLEEP_PERIOD],
                    "model": self.device_info["model"],
                    "gen": self.device_info["gen"],
                },
            )

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "model": get_model_name(self.info),
                "host": self.host,
            },
            errors=errors,
        )

    async def _async_get_info(self, host: str) -> dict[str, Any]:
        """Get info from shelly device."""
        async with async_timeout.timeout(AIOSHELLY_DEVICE_TIMEOUT_SEC):
            return await aioshelly.common.get_info(
                aiohttp_client.async_get_clientsession(self.hass), host
            )
