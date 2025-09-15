"""Config flow for the Victron Energy integration."""

from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import CONF_BROKER, CONF_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BROKER, default="venus.local"): str,
        vol.Required(CONF_PORT, default=1883): int,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    # Here we validate that the data provided by the user is valid.
    # Broker and Port are required, username and password are optional.
    # If the data seems correct, we can proceed to set up the connection.

    # Make sure the hostname is either an IP address or a valid hostname.
    broker = data[CONF_BROKER]

    # Check if broker is a valid IP address
    try:
        ipaddress.ip_address(broker)
    except ValueError as err:
        hostname_regex = re.compile(
            r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
        )
        if not hostname_regex.match(broker):
            raise CannotConnect(
                "Broker is not a valid IP address or hostname."
            ) from err

    # Check if port is a valid integer
    if not isinstance(data[CONF_PORT], int) or not (0 < data[CONF_PORT] < 65536):
        raise CannotConnect("Port must be an integer between 1 and 65535.")

    #  TO-DO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
    # )

    # hub = PlaceholderHub(data[CONF_BROKER])

    # if not await hub.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD]):
    #     raise InvalidAuth

    # Username and password are optional, so you can check if they are provided
    # and handle them accordingly.
    # But broker and port are required
    if not data[CONF_BROKER] or not data[CONF_PORT]:
        raise CannotConnect
    # If you have a real library, you can use it to connect to the device.

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    # Ensure all returned values are str for mypy compatibility
    return {"title": "Venus OS Hub", "host": str(data[CONF_BROKER])}


class VictronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Victron Energy."""

    VERSION = 1
    # CONNECTION_CLASS = ConfigFlow.CONNECTION_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=str(info["title"]), data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""

        # Debug
        _LOGGER.debug("Discovered SSDP info: %s", discovery_info)

        host = discovery_info.ssdp_headers.get("_host")
        friendly_name = discovery_info.upnp.get("friendlyName", "Victron Energy GX")
        unique_id = discovery_info.upnp.get("X_VrmPortalId")
        if unique_id is None:
            return self.async_abort(reason="missing_unique_id")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(
            updates={
                CONF_BROKER: host,
            }
        )

        self.context["title_placeholders"] = {
            "name": friendly_name,
            "host": str(host or ""),
        }
        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER, default=host): str,
                    vol.Required(CONF_PORT, default=1883): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle submission of the SSDP discovery form."""
        errors: dict[str, str] = {}
        host = self.context.get("title_placeholders", {}).get("host", "")
        if user_input is not None:
            # Merge discovered host with user input
            user_input = {**user_input, CONF_BROKER: host}
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=host or "Victron Energy", data=user_input
                )

        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER, default=host): str,
                    vol.Required(CONF_PORT, default=1883): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=self.context.get("title_placeholders", {}),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to confirm adding the device."""
        errors: dict[str, str] = {}
        host = self.context.get("title_placeholders", {}).get("host", "")
        if user_input is not None:
            # Merge discovered host with user input
            user_input = {**user_input, CONF_BROKER: host}
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=host or "Victron Energy", data=user_input
                )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BROKER, default=host): str,
                    vol.Required(CONF_PORT, default=1883): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=self.context.get("title_placeholders", {}),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
