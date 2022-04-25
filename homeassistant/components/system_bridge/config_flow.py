"""Config flow for System Bridge integration."""
from __future__ import annotations

import logging
from typing import Any

from systembridgeconnector.const import EVENT_TYPE, TYPE_DATA_UPDATE
from systembridgeconnector.exceptions import (
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.websocket_client import WebSocketClient
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.components import zeroconf
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_AUTHENTICATE_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=9170): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def validate_input(data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]

    websocket_client = WebSocketClient(
        host,
        data[CONF_PORT],
        data[CONF_API_KEY],
    )
    try:
        await websocket_client.connect()
    except ConnectionErrorException as exception:
        _LOGGER.info(exception)
        raise CannotConnect from exception

    await websocket_client.get_data(["system"])
    try:
        while True:
            result = await websocket_client.listen_for_message()
            if result[EVENT_TYPE] == TYPE_DATA_UPDATE:
                break
            _LOGGER.info("Message: %s", result)
    except ConnectionClosedException as exception:
        _LOGGER.info(exception)
        raise CannotConnect from exception

    _LOGGER.info("%s Message: %s", TYPE_DATA_UPDATE, result)

    if "uuid" not in result["data"]:
        error = "No UUID in result!"
        _LOGGER.info(error)
        raise Exception(error)

    return {"hostname": host, "uuid": result["data"]["uuid"]}


async def _async_get_info(
    user_input: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str] | None]:
    errors = {}

    try:
        info = await validate_input(user_input)
    except CannotConnect:
        errors["base"] = "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    else:
        return errors, info

    return errors, None


class ConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for System Bridge."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._name: str | None = None
        self._input: dict[str, Any] = {}
        self._reauth = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors, info = await _async_get_info(user_input)
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
    ) -> FlowResult:
        """Handle getting the api-key for authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**self._input, **user_input}
            errors, info = await _async_get_info(user_input)
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
    ) -> FlowResult:
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

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._name = entry_data[CONF_HOST]
        self._input = {
            CONF_HOST: entry_data[CONF_HOST],
            CONF_PORT: entry_data[CONF_PORT],
        }
        self._reauth = True
        return await self.async_step_authenticate()


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
