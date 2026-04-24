"""Config flow for SAJ."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pysaj
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import CONNECTION_TYPES, DOMAIN, INTEGRATION_TITLE

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid credentials (config flow)."""


class SAJConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the SAJ Solar Inverter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._connection_type: str | None = None
        self._pending_username: str = ""
        self._pending_password: str = ""

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml (sensor platform)."""
        _LOGGER.warning("Importing SAJ from YAML is deprecated and will be removed")
        entry_input: dict[str, Any] = {
            CONF_HOST: import_config[CONF_HOST],
            CONF_TYPE: import_config.get(CONF_TYPE, CONNECTION_TYPES[0]),
            CONF_USERNAME: import_config.get(CONF_USERNAME),
            CONF_PASSWORD: import_config.get(CONF_PASSWORD),
        }
        try:
            serial_number = await self._async_validate_input(entry_input)
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error importing SAJ from YAML")
            return self.async_abort(reason="unknown")

        data = {
            CONF_HOST: entry_input[CONF_HOST],
            CONF_TYPE: entry_input[CONF_TYPE],
            CONF_USERNAME: entry_input.get(CONF_USERNAME),
            CONF_PASSWORD: entry_input.get(CONF_PASSWORD),
        }
        title = (import_config.get(CONF_NAME) or "").strip() or INTEGRATION_TITLE

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured(updates=data)

        return self.async_create_entry(title=title, data=data)

    async def _async_validate_input(self, user_input: dict[str, Any]) -> str:
        """Validate the user input allows us to connect.

        Returns the device serial number (required after a successful read).
        """
        host = user_input[CONF_HOST]
        connection_type = user_input[CONF_TYPE]
        username = user_input.get(CONF_USERNAME)
        password = user_input.get(CONF_PASSWORD)

        wifi = connection_type == CONNECTION_TYPES[1]
        kwargs: dict[str, Any] = {}
        if wifi:
            kwargs["wifi"] = True
            if username:
                kwargs["username"] = username
            if password:
                kwargs["password"] = password

        async def _async_validate_connection() -> str:
            """Validate connection and get serial number."""
            saj = pysaj.SAJ(host, **kwargs)
            sensor_def = pysaj.Sensors(wifi)
            done = await saj.read(sensor_def)
            if not done:
                raise CannotConnect("Failed to read sensor data")

            serial_number = saj.serialnumber
            if not serial_number:
                raise CannotConnect("Device did not return a serial number")
            return serial_number

        try:
            serial_number = await _async_validate_connection()

        except pysaj.UnauthorizedException as err:
            # Only raise auth error for WiFi connections with wrong credentials
            if wifi:
                raise InvalidAuth("Invalid authentication") from err
            # For ethernet, this likely means wrong connection type - treat as connection error
            raise CannotConnect("Wrong connection type or cannot connect") from err
        except pysaj.UnexpectedResponseException as err:
            raise CannotConnect(f"Connection error: {err}") from err
        except Exception as err:
            raise CannotConnect(f"Connection failed: {err}") from err

        return serial_number

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            connection_type = user_input.get(CONF_TYPE, CONNECTION_TYPES[0])

            # Store host/type for a possible WiFi credentials step
            self._host = host
            self._connection_type = connection_type
            self._pending_username = user_input.get(CONF_USERNAME) or ""
            self._pending_password = user_input.get(CONF_PASSWORD) or ""

            entry_input = {
                CONF_HOST: host,
                CONF_TYPE: connection_type,
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            # Ethernet ignores username/password; WiFi tries open access or creds from this step
            try:
                serial_number = await self._async_validate_input(entry_input)
            except InvalidAuth:
                # WiFi-only: device is SAJ but requires credentials
                return await self.async_step_device_credentials()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during user flow")
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_HOST: entry_input[CONF_HOST],
                    CONF_TYPE: entry_input[CONF_TYPE],
                    CONF_USERNAME: entry_input.get(CONF_USERNAME),
                    CONF_PASSWORD: entry_input.get(CONF_PASSWORD),
                }

                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(updates=data)

                return self.async_create_entry(title=INTEGRATION_TITLE, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema_user(),
            errors=errors or None,
        )

    def _schema_user(self) -> vol.Schema:
        """Define the schema for the user step."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_TYPE, default=CONNECTION_TYPES[0]): vol.In(
                    CONNECTION_TYPES
                ),
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
            }
        )

    async def async_step_device_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device credentials step (only shown for WiFi connections)."""
        errors = {}

        if user_input is not None:
            if TYPE_CHECKING:
                assert self._host is not None
                assert self._connection_type is not None

            combined_input = {
                CONF_HOST: self._host,
                CONF_TYPE: self._connection_type,
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            try:
                serial_number = await self._async_validate_input(combined_input)
                data = {
                    CONF_HOST: combined_input[CONF_HOST],
                    CONF_TYPE: combined_input[CONF_TYPE],
                    CONF_USERNAME: combined_input.get(CONF_USERNAME),
                    CONF_PASSWORD: combined_input.get(CONF_PASSWORD),
                }
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during device credentials flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(updates=data)

                return self.async_create_entry(title=INTEGRATION_TITLE, data=data)
        return self.async_show_form(
            step_id="device_credentials",
            data_schema=self._schema_device_credentials(),
            errors=errors or None,
        )

    def _schema_device_credentials(self) -> vol.Schema:
        """Define the schema for the device credentials step."""
        return vol.Schema(
            {
                vol.Optional(CONF_USERNAME, default=self._pending_username): str,
                vol.Optional(CONF_PASSWORD, default=self._pending_password): str,
            }
        )
