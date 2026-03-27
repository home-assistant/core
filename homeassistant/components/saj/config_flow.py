"""Config flow for SAJ."""

from __future__ import annotations

import logging
from typing import Any

import pysaj
import voluptuous as vol

from homeassistant import data_entry_flow
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

from .const import CONNECTION_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid credentials (config flow)."""


def _config_entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize user input into config entry data."""
    return {
        CONF_HOST: user_input[CONF_HOST],
        CONF_TYPE: user_input[CONF_TYPE],
        CONF_USERNAME: user_input.get(CONF_USERNAME) or "",
        CONF_PASSWORD: user_input.get(CONF_PASSWORD) or "",
    }


class SAJConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the SAJ Solar Inverter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._host: str | None = None
        self._connection_type: str | None = None
        self._pending_entry_name: str = "SAJ Solar Inverter"
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
        except data_entry_flow.AbortFlow:
            raise
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error importing SAJ from YAML")
            return self.async_abort(reason="unknown")

        data = _config_entry_data(entry_input)
        title = (import_config.get(CONF_NAME) or "").strip() or "SAJ Solar Inverter"

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
                _LOGGER.error("Username and/or password is wrong for host %s", host)
                raise InvalidAuth("Invalid authentication") from err
            # For ethernet, this likely means wrong connection type - treat as connection error
            _LOGGER.error(
                "Connection failed for host %s (wrong connection type?): %s", host, err
            )
            raise CannotConnect("Wrong connection type or cannot connect") from err
        except pysaj.UnexpectedResponseException as err:
            _LOGGER.error("Error connecting to SAJ at %s: %s", host, err)
            raise CannotConnect(f"Connection error: {err}") from err
        except Exception as err:
            _LOGGER.error("Connection failed for host %s: %s", host, err)
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
            self._pending_entry_name = (
                user_input.get(CONF_NAME) or ""
            ).strip() or "SAJ Solar Inverter"
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
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                _LOGGER.debug("Connection failed: %s", err)
            except data_entry_flow.AbortFlow:
                raise  # Let AbortFlow propagate (e.g., already_configured)
            except Exception:
                _LOGGER.exception("Unexpected error during user flow")
                errors["base"] = "unknown"
            else:
                data = _config_entry_data(entry_input)

                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(updates=data)

                return self.async_create_entry(
                    title=self._pending_entry_name, data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema_user(),
            errors=errors or None,
        )

    def _schema_user(self) -> vol.Schema:
        """Define the schema for the user step."""
        return vol.Schema(
            {
                vol.Optional(CONF_NAME, default="SAJ Solar Inverter"): str,
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
            # Ensure required connection parameters are available
            if self._host is None or self._connection_type is None:
                _LOGGER.error(
                    "Missing host or connection type when handling device credentials step"
                )
                errors["base"] = "unknown"
            else:
                # Combine data from both steps
                combined_input = {
                    CONF_HOST: self._host,
                    CONF_TYPE: self._connection_type,
                    CONF_USERNAME: user_input.get(CONF_USERNAME, "") or "",
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD, "") or "",
                }

                try:
                    serial_number = await self._async_validate_input(combined_input)
                    data = _config_entry_data(combined_input)
                except InvalidAuth as err:
                    errors["base"] = "invalid_auth"
                    _LOGGER.debug("Authentication failed: %s", err)
                except CannotConnect as err:
                    errors["base"] = "cannot_connect"
                    _LOGGER.debug("Connection failed: %s", err)
                except data_entry_flow.AbortFlow:
                    raise  # Let AbortFlow propagate (e.g., already_configured)
                except Exception:
                    _LOGGER.exception("Unexpected error during device credentials flow")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured(updates=data)

                    title = (
                        user_input.get(CONF_NAME) or ""
                    ).strip() or self._pending_entry_name
                    return self.async_create_entry(title=title, data=data)
        return self.async_show_form(
            step_id="device_credentials",
            data_schema=self._schema_device_credentials(),
            errors=errors or None,
        )

    def _schema_device_credentials(self) -> vol.Schema:
        """Define the schema for the device credentials step."""
        return vol.Schema(
            {
                vol.Optional(CONF_NAME, default=self._pending_entry_name): str,
                vol.Optional(CONF_USERNAME, default=self._pending_username): str,
                vol.Optional(CONF_PASSWORD, default=self._pending_password): str,
            }
        )
