"""Config flow for the Ubiquiti airOS integration."""

from __future__ import annotations

import logging
from typing import Any

from airos.airos8 import AirOS
from airos.exceptions import (
    ConnectionAuthenticationError,
    ConnectionSetupError,
    DataMissingError,
    DeviceConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, default="ubnt"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    session = async_get_clientsession(hass, verify_ssl=False)
    airos_device = AirOS(
        host=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
    )

    try:
        await airos_device.login()
        status = await airos_device.status()

        host_data: dict = status["host"]
        device_id: str = host_data["device_id"]
        hostname: str = host_data.get("hostname", "Ubiquiti airOS Device")

        device_data: dict = {
            "title": hostname,
            "device_id": device_id,
            "hostname": hostname,
            "data": status,
        }
    except (
        ConnectionSetupError,
        DeviceConnectionError,
    ) as e:
        _LOGGER.error("Error connecting to airOS device: %s", e)
        raise CannotConnect from e
    except (
        ConnectionAuthenticationError,
        DataMissingError,
    ) as e:
        _LOGGER.error("Error authenticating with airOS device: %s", e)
        raise InvalidAuth from e
    except KeyError as e:
        # Handle unexpected data structure and missing device-id
        _LOGGER.error("Unexpected data returned by airOS device: %s", e)
        raise KeyError from e

    return device_data


class AirOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ubiquiti airOS."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_data = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_data.get("device_id"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_data.get("title", "Ubiquity airOS"), data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
