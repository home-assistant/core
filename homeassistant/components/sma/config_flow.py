"""Config flow for the sma integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import pysma
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_CUSTOM, CONF_GROUP, DEVICE_INFO, DOMAIN, GROUPS

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass, verify_ssl=data[CONF_VERIFY_SSL])

    protocol = "https" if data[CONF_SSL] else "http"
    url = f"{protocol}://{data[CONF_HOST]}"

    sma = pysma.SMA(session, url, data[CONF_PASSWORD], group=data[CONF_GROUP])

    if await sma.new_session() is False:
        raise InvalidAuth

    device_info = await sma.device_info()
    await sma.close_session()

    if not device_info:
        raise CannotRetrieveDeviceInfo

    return device_info


class SmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMA."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._data = {
            CONF_HOST: vol.UNDEFINED,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
            CONF_GROUP: GROUPS[0],
            CONF_PASSWORD: vol.UNDEFINED,
            CONF_SENSORS: [],
            CONF_CUSTOM: {},
            DEVICE_INFO: {},
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step in config flow."""
        errors = {}
        if user_input is not None:
            self._data[CONF_HOST] = user_input[CONF_HOST]
            self._data[CONF_SSL] = user_input[CONF_SSL]
            self._data[CONF_VERIFY_SSL] = user_input[CONF_VERIFY_SSL]
            self._data[CONF_GROUP] = user_input[CONF_GROUP]
            self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            try:
                self._data[DEVICE_INFO] = await validate_input(self.hass, user_input)
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotRetrieveDeviceInfo:
                errors["base"] = "cannot_retrieve_device_info"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(self._data[DEVICE_INFO]["serial"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._data[CONF_HOST]): cv.string,
                    vol.Optional(CONF_SSL, default=self._data[CONF_SSL]): cv.boolean,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=self._data[CONF_VERIFY_SSL]
                    ): cv.boolean,
                    vol.Optional(CONF_GROUP, default=self._data[CONF_GROUP]): vol.In(
                        GROUPS
                    ),
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any] | None
    ) -> FlowResult:
        """Import a config flow from configuration."""
        device_info = await validate_input(self.hass, import_config)
        import_config[DEVICE_INFO] = device_info

        # If unique is configured import was already run
        # This means remap was already done, so we can abort
        await self.async_set_unique_id(device_info["serial"])
        self._abort_if_unique_id_configured(import_config)

        return self.async_create_entry(
            title=import_config[CONF_HOST], data=import_config
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CannotRetrieveDeviceInfo(exceptions.HomeAssistantError):
    """Error to indicate we cannot retrieve the device information."""
