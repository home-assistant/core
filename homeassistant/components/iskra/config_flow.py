"""Config flow for iskra integration."""

from __future__ import annotations

import logging
from typing import Any

from pyiskra.adapters import Modbus, RestAPI
from pyiskra.exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    InvalidResponseCode,
    NotAuthorised,
)
from pyiskra.helper import BasicInfo
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PROTOCOL, default="rest_api"): SelectSelector(
            SelectSelectorConfig(
                options=["rest_api", "modbus_tcp"],
                mode=SelectSelectorMode.LIST,
                translation_key="protocol",
            ),
        ),
    }
)

STEP_AUTHENTICATION_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

# CONF_ADDRESS validation is done later in code, as if ranges are set in voluptuous it turns into a slider
STEP_MODBUS_TCP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT, default=10001): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=65535)
        ),
        vol.Required(CONF_ADDRESS, default=33): NumberSelector(
            NumberSelectorConfig(min=1, max=255, mode=NumberSelectorMode.BOX)
        ),
    }
)


async def test_rest_api_connection(host: str, user_input: dict[str, Any]) -> BasicInfo:
    """Check if the RestAPI requires authentication."""

    rest_api = RestAPI(ip_address=host, authentication=user_input)
    try:
        basic_info = await rest_api.get_basic_info()
    except NotAuthorised as e:
        raise NotAuthorised from e
    except (DeviceConnectionError, DeviceTimeoutError, InvalidResponseCode) as e:
        raise CannotConnect from e
    except Exception as e:
        _LOGGER.error("Unexpected exception: %s", e)
        raise UnknownException from e

    return basic_info


async def test_modbus_connection(host: str, user_input: dict[str, Any]) -> BasicInfo:
    """Test the Modbus connection."""
    modbus_api = Modbus(
        ip_address=host,
        protocol="tcp",
        port=user_input[CONF_PORT],
        modbus_address=user_input[CONF_ADDRESS],
    )

    try:
        basic_info = await modbus_api.get_basic_info()
    except NotAuthorised as e:
        raise NotAuthorised from e
    except (DeviceConnectionError, DeviceTimeoutError, InvalidResponseCode) as e:
        raise CannotConnect from e
    except Exception as e:
        _LOGGER.error("Unexpected exception: %s", e)
        raise UnknownException from e

    return basic_info


class IskraConfigFlowFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iskra."""

    VERSION = 1
    host: str
    protocol: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.protocol = user_input[CONF_PROTOCOL]
            if self.protocol == "rest_api":
                # Check if authentication is required.
                try:
                    device_info = await test_rest_api_connection(self.host, user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except NotAuthorised:
                    # Proceed to authentication step.
                    return await self.async_step_authentication()
                except UnknownException:
                    errors["base"] = "unknown"
                    # If the connection was not successful, show an error.

                # If the connection was successful, create the device.
                if not errors:
                    return await self._create_entry(
                        host=self.host,
                        protocol=self.protocol,
                        device_info=device_info,
                        user_input=user_input,
                    )

            if self.protocol == "modbus_tcp":
                # Proceed to modbus step.
                return await self.async_step_modbus_tcp()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_authentication(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the authentication step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device_info = await test_rest_api_connection(self.host, user_input)
            # If the connection failed, abort.
            except CannotConnect:
                errors["base"] = "cannot_connect"
            # If the authentication failed, show an error and authentication form again.
            except NotAuthorised:
                errors["base"] = "invalid_auth"
            except UnknownException:
                errors["base"] = "unknown"

            # if the connection was successful, create the device.
            if not errors:
                return await self._create_entry(
                    self.host,
                    self.protocol,
                    device_info=device_info,
                    user_input=user_input,
                )

        # If there's no user_input or there was an error, show the authentication form again.
        return self.async_show_form(
            step_id="authentication",
            data_schema=STEP_AUTHENTICATION_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_modbus_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the Modbus TCP step."""
        errors: dict[str, str] = {}

        # If there's user_input, check the connection.
        if user_input is not None:
            # convert to integer
            user_input[CONF_ADDRESS] = int(user_input[CONF_ADDRESS])

            try:
                device_info = await test_modbus_connection(self.host, user_input)

            # If the connection failed, show an error.
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except UnknownException:
                errors["base"] = "unknown"

            # If the connection was successful, create the device.
            if not errors:
                return await self._create_entry(
                    host=self.host,
                    protocol=self.protocol,
                    device_info=device_info,
                    user_input=user_input,
                )

        # If there's no user_input or there was an error, show the modbus form again.
        return self.async_show_form(
            step_id="modbus_tcp",
            data_schema=STEP_MODBUS_TCP_DATA_SCHEMA,
            errors=errors,
        )

    async def _create_entry(
        self,
        host: str,
        protocol: str,
        device_info: BasicInfo,
        user_input: dict[str, Any],
    ) -> ConfigFlowResult:
        """Create the config entry."""

        await self.async_set_unique_id(device_info.serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=device_info.model,
            data={CONF_HOST: host, CONF_PROTOCOL: protocol, **user_input},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class UnknownException(HomeAssistantError):
    """Error to indicate an unknown exception occurred."""
