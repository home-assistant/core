"""Config flow for SAJ."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

import pysaj
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_MAC, CONNECTION_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 2.0


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


async def _validate_saj_device(
    host: str, connection_type: str = CONNECTION_TYPES[0]
) -> tuple[str, str]:
    """Validate that the device at host is an SAJ inverter.

    Returns tuple of (unique_id, hostname/model).
    Raises CannotConnect if validation fails.
    """
    wifi = connection_type == CONNECTION_TYPES[1]
    kwargs: dict[str, Any] = {}
    if wifi:
        kwargs["wifi"] = True

    async def _async_validate_device() -> tuple[str, str]:
        """Validate device connection and get unique_id."""
        saj = pysaj.SAJ(host, **kwargs)
        sensor_def = pysaj.Sensors(wifi)

        async with asyncio.timeout(DISCOVERY_TIMEOUT):
            done = await saj.read(sensor_def)
            if not done:
                raise CannotConnect("Failed to read sensor data")

        # Get serial number for unique_id
        serial_number = saj.serialnumber
        if not serial_number:
            raise CannotConnect("No serial number found")

        # Use serial number as unique_id
        unique_id = serial_number
        title = "SAJ Solar Inverter"

        return unique_id, title

    try:
        return await _async_validate_device()

    except TimeoutError as err:
        _LOGGER.debug("Timeout validating SAJ device at %s: %s", host, err)
        raise CannotConnect("Connection timeout") from err
    except pysaj.UnauthorizedException as err:
        _LOGGER.debug("Authentication required for %s", host)
        raise CannotConnect("Authentication required") from err
    except pysaj.UnexpectedResponseException as err:
        _LOGGER.debug("Unexpected response from %s: %s", host, err)
        raise CannotConnect("Not an SAJ device") from err
    except Exception as err:
        _LOGGER.debug("Error validating SAJ device at %s: %s", host, err)
        raise CannotConnect(f"Connection error: {err}") from err


class SAJConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the SAJ Solar Inverter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.discovery_info: dict[str, Any] = {}
        self._host: str | None = None
        self._connection_type: str | None = None

    async def _async_validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[Mapping[str, Any], str | None]:
        """Validate the user input allows us to connect.

        Returns tuple of (data dict, serial_number).
        """
        host = user_input["host"]
        connection_type = user_input["type"]
        username = user_input.get("username")
        password = user_input.get("password")

        wifi = connection_type == CONNECTION_TYPES[1]
        kwargs: dict[str, Any] = {}
        if wifi:
            kwargs["wifi"] = True
            if username:
                kwargs["username"] = username
            if password:
                kwargs["password"] = password

        async def _async_validate_connection() -> str | None:
            """Validate connection and get serial number."""
            saj = pysaj.SAJ(host, **kwargs)
            sensor_def = pysaj.Sensors(wifi)
            done = await saj.read(sensor_def)
            if not done:
                raise ConfigEntryAuthFailed("Failed to read sensor data")

            return saj.serialnumber

        try:
            serial_number = await _async_validate_connection()

        except pysaj.UnauthorizedException as err:
            # Only raise auth error for WiFi connections with wrong credentials
            if wifi:
                _LOGGER.error("Username and/or password is wrong for host %s", host)
                raise ConfigEntryAuthFailed("Invalid authentication") from err
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

        return {
            "host": host,
            "type": connection_type,
            "username": username or "",
            "password": password or "",
        }, serial_number

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow started by the user."""
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            connection_type = user_input.get("type", CONNECTION_TYPES[0])

            # Store for next step if WiFi is selected
            self._host = host
            self._connection_type = connection_type

            # If WiFi is selected, proceed to credentials step
            if connection_type == CONNECTION_TYPES[1]:
                return await self.async_step_device_credentials()

            # For Ethernet, validate and create entry directly
            try:
                data, serial_number = await self._async_validate_input(
                    user_input={"host": host, "type": connection_type}
                )

                # Set unique_id if we got a serial number
                if serial_number:
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured(updates=dict(data))

                return self.async_create_entry(
                    title=user_input.get("name", "SAJ Solar Inverter"), data=data
                )
            except ConfigEntryAuthFailed as err:
                errors["base"] = "invalid_auth"
                _LOGGER.debug("Authentication failed: %s", err)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                _LOGGER.debug("Connection failed: %s", err)
            except data_entry_flow.AbortFlow:
                raise  # Let AbortFlow propagate (e.g., already_configured)
            except Exception:
                _LOGGER.exception("Unexpected error during user flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema_user(),
            errors=errors or None,
        )

    def _schema_user(self) -> vol.Schema:
        """Define the schema for the user step (host and connection type)."""
        return vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("type", default=CONNECTION_TYPES[0]): vol.In(
                    CONNECTION_TYPES
                ),
            }
        )

    async def async_step_device_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device credentials step (only shown for WiFi connections)."""
        errors = {}

        if user_input is not None:
            # Combine data from both steps
            combined_input = {
                "host": self._host,
                "type": self._connection_type,
                "username": user_input.get("username", None),
                "password": user_input.get("password", None),
            }

            try:
                data, serial_number = await self._async_validate_input(
                    user_input=combined_input
                )

                # Set unique_id if we got a serial number
                if serial_number:
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured(updates=dict(data))

                return self.async_create_entry(title="SAJ Solar Inverter", data=data)
            except ConfigEntryAuthFailed as err:
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

        return self.async_show_form(
            step_id="device_credentials",
            data_schema=self._schema_device_credentials(),
            errors=errors or None,
        )

    def _schema_device_credentials(self) -> vol.Schema:
        """Define the schema for device credentials step."""
        return vol.Schema(
            {
                vol.Optional("username", default=""): str,
                vol.Optional("password", default=""): str,
            }
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        host = discovery_info.ip
        hostname = discovery_info.hostname or ""
        macaddress = discovery_info.macaddress

        _LOGGER.info(
            "DHCP discovery triggered: host=%s, hostname=%s, mac=%s",
            host,
            hostname,
            macaddress,
        )

        # Check if hostname or MAC matches our patterns
        hostname_match = hostname.lower().startswith("saj-") if hostname else False
        mac_match = (
            macaddress.replace(":", "").upper().startswith("441793")
            if macaddress
            else False
        )
        _LOGGER.debug(
            "DHCP match check: hostname_match=%s, mac_match=%s",
            hostname_match,
            mac_match,
        )

        # Try to validate device and get unique_id
        mac_unique_id = macaddress.replace(":", "").upper() if macaddress else None
        unique_id: str | None = None
        title: str | None = None
        connection_type = CONNECTION_TYPES[0]  # Default to ethernet

        # If MAC matches, check if we already have this device configured
        if mac_match and macaddress:
            formatted_mac = dr.format_mac(macaddress)
            dev_reg = dr.async_get(self.hass)
            if device := dev_reg.async_get_device(
                connections={(dr.CONNECTION_NETWORK_MAC, formatted_mac)}
            ):
                # Find the SAJ config entry for this device
                for entry_id in device.config_entries:
                    if (
                        entry := self.hass.config_entries.async_get_entry(entry_id)
                    ) and entry.domain == DOMAIN:
                        # Use the existing connection type
                        connection_type = entry.data.get(CONF_TYPE, CONNECTION_TYPES[0])
                        _LOGGER.debug(
                            "Found existing SAJ device with MAC %s, using connection type: %s",
                            formatted_mac,
                            connection_type,
                        )
                        break

        # Validate device - try ethernet first, then WiFi if that fails
        try:
            unique_id, title = await _validate_saj_device(host, CONNECTION_TYPES[0])
            connection_type = CONNECTION_TYPES[0]  # Ethernet
            _LOGGER.info(
                "Successfully validated SAJ ethernet device at %s with serial %s",
                host,
                unique_id,
            )
        except CannotConnect:
            # Ethernet failed - try WiFi if MAC matches or we have existing WiFi device
            if mac_match or connection_type == CONNECTION_TYPES[1]:
                _LOGGER.debug(
                    "Ethernet validation failed for %s, trying WiFi",
                    host,
                )
                try:
                    unique_id, title = await _validate_saj_device(
                        host, CONNECTION_TYPES[1]
                    )
                    connection_type = CONNECTION_TYPES[1]  # WiFi
                    _LOGGER.info(
                        "Successfully validated SAJ WiFi device at %s with serial %s",
                        host,
                        unique_id,
                    )
                except CannotConnect:
                    _LOGGER.debug(
                        "Both ethernet and WiFi validation failed for %s",
                        host,
                    )
                    return self.async_abort(reason="not_saj_device")
            else:
                # MAC doesn't match and ethernet failed - not an SAJ device
                _LOGGER.debug(
                    "Device at %s failed ethernet validation and MAC doesn't match SAJ pattern",
                    host,
                )
                return self.async_abort(reason="not_saj_device")

        # Set unique_id and check if already configured
        final_unique_id = unique_id or mac_unique_id
        if not final_unique_id:
            return self.async_abort(reason="no_unique_id")

        await self.async_set_unique_id(final_unique_id, raise_on_progress=False)

        # Check if entry exists - if IP changed, update it
        existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, final_unique_id
        )
        if existing_entry:
            current_ip = existing_entry.data.get(CONF_HOST)
            if current_ip != host:
                _LOGGER.info(
                    "Updating IP address for SAJ device %s from %s to %s",
                    final_unique_id,
                    current_ip,
                    host,
                )
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            else:
                _LOGGER.debug(
                    "SAJ device %s already configured with IP %s",
                    final_unique_id,
                    host,
                )
                return self.async_abort(reason="already_configured")

        self._abort_if_unique_id_configured()

        # Store discovery info for confirmation step
        self.discovery_info = {
            CONF_HOST: host,
            CONF_TYPE: connection_type,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
        }
        # Store MAC address if available for future matching
        if macaddress:
            self.discovery_info[CONF_MAC] = dr.format_mac(macaddress)

        # Update context for confirmation
        self.context["title_placeholders"] = {"device": title or "SAJ Solar Inverter"}

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered SAJ inverter."""
        errors = {}

        # Check if this is a WiFi device that needs credentials
        is_wifi = self.discovery_info.get(CONF_TYPE) == CONNECTION_TYPES[1]

        if user_input is not None:
            if is_wifi:
                # For WiFi devices, validate with credentials
                try:
                    data, serial_number = await self._async_validate_input(
                        user_input={
                            "host": self.discovery_info[CONF_HOST],
                            "type": CONNECTION_TYPES[1],
                            "username": user_input.get("username", ""),
                            "password": user_input.get("password", ""),
                        }
                    )
                    # Update discovery_info with validated data
                    self.discovery_info.update(data)
                    # Update unique_id with serial number if available
                    if serial_number:
                        await self.async_set_unique_id(
                            serial_number, raise_on_progress=False
                        )
                        self._abort_if_unique_id_configured()
                except ConfigEntryAuthFailed:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Error validating WiFi device")
                    errors["base"] = "cannot_connect"

            if not errors:
                # Create entry with discovered/validated data
                return self.async_create_entry(
                    title=self.context.get("title_placeholders", {}).get(
                        "device", "SAJ Solar Inverter"
                    ),
                    data=self.discovery_info,
                )

        # Show form - for WiFi devices, include credential fields
        if is_wifi:
            data_schema = vol.Schema(
                {
                    vol.Optional("username", default=""): str,
                    vol.Optional("password", default=""): str,
                }
            )
            self._set_confirm_only()
            return self.async_show_form(
                step_id="confirm_discovery",
                data_schema=data_schema,
                description_placeholders={
                    "device": self.context.get("title_placeholders", {}).get(
                        "device", "SAJ Inverter"
                    ),
                },
                errors=errors or None,
            )

        # For Ethernet devices, simple confirmation
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "device": self.context.get("title_placeholders", {}).get(
                    "device", "SAJ Inverter"
                ),
            },
        )
