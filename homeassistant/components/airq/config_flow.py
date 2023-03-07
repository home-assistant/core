"""Config flow for air-Q integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aioairq
from aiohttp.client_exceptions import ClientConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for air-Q."""

    _reauth_unique_id: str | None = None
    VERSION = 1

    async def _async_validate_input(self, ip_address, password):
        errors = {}
        device_info = aioairq.DeviceInfo(id="placeholder_id")
        session = async_get_clientsession(self.hass)
        try:
            airq = aioairq.AirQ(ip_address, password, session)
            device_info = await airq.fetch_device_info()
        except aioairq.InvalidInput:
            _LOGGER.debug(
                "%s does not appear to be a valid IP address or mDNS name",
                ip_address,
            )
            errors["base"] = "invalid_input"
        except ClientConnectionError:
            _LOGGER.debug(
                "Failed to connect to device %s. Check the IP address / device ID "
                "as well as whether the device is connected to power and the WiFi",
                ip_address,
            )
            errors["base"] = "cannot_connect"
        except aioairq.InvalidAuth:
            _LOGGER.debug("Incorrect password for device %s", ip_address)
            errors["base"] = "invalid_auth"
        except aioairq.InvalidAirQResponse:
            _LOGGER.debug(
                "Successfully connected, but unable to retrieve information for device %s",
                ip_address,
            )
            errors["base"] = "cannot_retrieve_device_info"

        return device_info, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial (authentication) configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_info, errors = await self._async_validate_input(
                user_input[CONF_IP_ADDRESS], user_input[CONF_PASSWORD]
            )

            if not errors:
                _LOGGER.debug(
                    "Successfully connected to %s", user_input[CONF_IP_ADDRESS]
                )

                await self.async_set_unique_id(device_info.pop("id"))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=device_info["name"],
                    data=user_input | {"device_info": device_info},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_unique_id = self.context["unique_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        existing_entry = await self.async_set_unique_id(self._reauth_unique_id)
        assert existing_entry is not None
        if user_input is not None:
            _, errors = await self._async_validate_input(
                existing_entry.data[CONF_IP_ADDRESS], user_input[CONF_PASSWORD]
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        **user_input,
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                CONF_IP_ADDRESS: existing_entry.data[CONF_IP_ADDRESS]
            },
        )
