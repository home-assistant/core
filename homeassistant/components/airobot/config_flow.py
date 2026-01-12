"""Config flow for the Airobot integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pyairobotrest import AirobotClient
from pyairobotrest.exceptions import (
    AirobotAuthError,
    AirobotConnectionError,
    AirobotError,
    AirobotTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as BaseConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


@dataclass
class DeviceInfo:
    """Device information."""

    title: str
    device_id: str


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> DeviceInfo:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)

    client = AirobotClient(
        host=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
    )

    try:
        # Try to fetch data to validate connection and authentication
        status = await client.get_statuses()
        settings = await client.get_settings()
    except AirobotAuthError as err:
        raise InvalidAuth from err
    except (AirobotConnectionError, AirobotTimeoutError, AirobotError) as err:
        raise CannotConnect from err

    # Use device name or device ID as title
    title = settings.device_name or status.device_id

    return DeviceInfo(title=title, device_id=status.device_id)


class AirobotConfigFlow(BaseConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airobot."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_mac: str | None = None
        self._discovered_device_id: str | None = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        # Store the discovered IP address and MAC
        self._discovered_host = discovery_info.ip
        self._discovered_mac = discovery_info.macaddress

        # Extract device_id from hostname (format: airobot-thermostat-t01xxxxxx)
        hostname = discovery_info.hostname.lower()
        device_id = hostname.replace("airobot-thermostat-", "").upper()
        self._discovered_device_id = device_id
        # Set unique_id to device_id for duplicate detection
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        # Show the confirmation form
        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle DHCP discovery confirmation - ask for credentials only."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine discovered host and device_id with user-provided password
            data = {
                CONF_HOST: self._discovered_host,
                CONF_USERNAME: self._discovered_device_id,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            try:
                info = await validate_input(self.hass, data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Store MAC address in config entry data
                if self._discovered_mac:
                    data[CONF_MAC] = self._discovered_mac

                return self.async_create_entry(title=info.title, data=data)

        # Only ask for password since we already have the device_id from discovery
        return self.async_show_form(
            step_id="dhcp_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "host": self._discovered_host or "",
                "device_id": self._discovered_device_id or "",
            },
            errors=errors,
        )

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
                # Use device ID as unique ID to prevent duplicates
                await self.async_set_unique_id(info.device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

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
                # Verify the device ID matches the existing config entry
                await self.async_set_unique_id(info.device_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                    title=info.title,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            # Combine existing data with new password
            data = {
                CONF_HOST: reauth_entry.data[CONF_HOST],
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            try:
                await validate_input(self.hass, data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "username": reauth_entry.data[CONF_USERNAME],
                "host": reauth_entry.data[CONF_HOST],
            },
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
