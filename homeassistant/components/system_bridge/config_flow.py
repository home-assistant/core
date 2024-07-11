"""Config flow for System Bridge integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.websocket_client import WebSocketClient
from systembridgemodels.modules import GetData
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .data import SystemBridgeData

_LOGGER = logging.getLogger(__name__)

STEP_AUTHENTICATE_DATA_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): cv.string})
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=9170): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
    }
)


async def _validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    system_bridge_data = SystemBridgeData()

    async def _async_handle_module(
        module_name: str,
        module: Any,
    ) -> None:
        """Handle data from the WebSocket client."""
        _LOGGER.debug("Set new data for: %s", module_name)
        setattr(system_bridge_data, module_name, module)

    websocket_client = WebSocketClient(
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_TOKEN],
        session=async_get_clientsession(hass),
    )

    try:
        async with asyncio.timeout(15):
            await websocket_client.connect()
            hass.async_create_task(
                websocket_client.listen(callback=_async_handle_module)
            )
            response = await websocket_client.get_data(GetData(modules=["system"]))
            _LOGGER.debug("Got response: %s", response)
            if response is None:
                raise CannotConnect("No data received")
            while system_bridge_data.system is None:
                await asyncio.sleep(0.2)
    except AuthenticationException as exception:
        _LOGGER.warning(
            "Authentication error when connecting to %s: %s",
            data[CONF_HOST],
            exception,
        )
        raise InvalidAuth from exception
    except (
        ConnectionClosedException,
        ConnectionErrorException,
    ) as exception:
        _LOGGER.warning(
            "Connection error when connecting to %s: %s", data[CONF_HOST], exception
        )
        raise CannotConnect from exception
    except TimeoutError as exception:
        _LOGGER.warning("Timed out connecting to %s: %s", data[CONF_HOST], exception)
        raise CannotConnect from exception
    except ValueError as exception:
        raise CannotConnect from exception

    _LOGGER.debug("Got System data: %s", system_bridge_data.system)

    return {"hostname": data[CONF_HOST], "uuid": system_bridge_data.system.uuid}


async def _async_get_info(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str] | None]:
    errors = {}

    try:
        info = await _validate_input(hass, user_input)
    except CannotConnect:
        errors["base"] = "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        return errors, info

    return errors, None


class SystemBridgeConfigFlow(
    ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for System Bridge."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._name: str | None = None
        self._input: dict[str, Any] = {}
        self._reauth = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors, info = await _async_get_info(self.hass, user_input)
        if not errors and info is not None:
            # Check if already configured
            await self.async_set_unique_id(info["uuid"], raise_on_progress=False)
            self._abort_if_unique_id_configured(updates={CONF_HOST: info["hostname"]})

            return self.async_create_entry(title=info["hostname"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_authenticate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle getting the api-key for authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**self._input, **user_input}
            errors, info = await _async_get_info(self.hass, user_input)
            if not errors and info is not None:
                # Check if already configured
                existing_entry = await self.async_set_unique_id(info["uuid"])

                if self._reauth and existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: info["hostname"]}
                )

                return self.async_create_entry(title=info["hostname"], data=user_input)

        return self.async_show_form(
            step_id="authenticate",
            data_schema=STEP_AUTHENTICATE_DATA_SCHEMA,
            description_placeholders={"name": self._name},
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        properties = discovery_info.properties
        host = properties.get("ip")
        uuid = properties.get("uuid")

        if host is None or uuid is None:
            return self.async_abort(reason="unknown")

        # Check if already configured
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._name = host
        self._input = {
            CONF_HOST: host,
            CONF_PORT: properties.get("port"),
        }

        return await self.async_step_authenticate()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._name = entry_data[CONF_HOST]
        self._input = {
            CONF_HOST: entry_data[CONF_HOST],
            CONF_PORT: entry_data[CONF_PORT],
        }
        self._reauth = True
        return await self.async_step_authenticate()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
