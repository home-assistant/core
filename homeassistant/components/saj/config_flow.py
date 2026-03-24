"""Config flow for SAJ."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from fnmatch import fnmatch
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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MAC, CONNECTION_TYPES, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 2.0

# Keep in sync with manifest.json dhcp matchers (hostname / macaddress).
_DHCP_SAJ_HOSTNAME_PATTERN = "saj-*"
_SAJ_MAC_OUI_PREFIX = "441793"


def _dhcp_should_try_wifi_after_ethernet_fails(
    hostname: str, macaddress: str | None
) -> bool:
    """Return True if DHCP hints match SAJ (hostname or OUI), so a WiFi probe is justified."""
    if hostname.strip() and fnmatch(hostname.lower(), _DHCP_SAJ_HOSTNAME_PATTERN):
        return True
    if not macaddress:
        return False
    mac = macaddress.replace(":", "").replace("-", "").upper()
    return mac.startswith(_SAJ_MAC_OUI_PREFIX)


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


async def _validate_saj_device(
    host: str,
    connection_type: str = CONNECTION_TYPES[0],
    *,
    accept_wifi_auth_challenge: bool = False,
) -> tuple[str | None, str]:
    """Validate that the device at host is an SAJ inverter.

    Returns (serial_number, title) when a full sensor read succeeds; serial_number
    is always non-empty in that case.

    When accept_wifi_auth_challenge is True for WiFi, UnauthorizedException is
    turned into (None, title) without a read — callers that need a serial must
    obtain it elsewhere (e.g. DHCP uses MAC as unique_id).

    Raises CannotConnect if validation fails.
    """
    wifi = connection_type == CONNECTION_TYPES[1]
    kwargs: dict[str, Any] = {}
    if wifi:
        kwargs["wifi"] = True

    async def _async_validate_device() -> tuple[str | None, str]:
        """Validate device connection and get unique_id."""
        saj = pysaj.SAJ(host, **kwargs)
        sensor_def = pysaj.Sensors(wifi)

        async with asyncio.timeout(DISCOVERY_TIMEOUT):
            done = await saj.read(sensor_def)
            if not done:
                raise CannotConnect("Failed to read sensor data")

        serial_number = saj.serialnumber
        if not serial_number:
            raise CannotConnect("Device did not return a serial number")

        title = "SAJ Solar Inverter"

        return serial_number, title

    try:
        return await _async_validate_device()

    except TimeoutError as err:
        _LOGGER.debug("Timeout validating SAJ device at %s: %s", host, err)
        raise CannotConnect("Connection timeout") from err
    except pysaj.UnauthorizedException as err:
        if wifi and accept_wifi_auth_challenge:
            _LOGGER.debug(
                "SAJ WiFi at %s requires credentials; discovery continues without them",
                host,
            )
            return None, "SAJ Solar Inverter"
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
        self._pending_entry_name: str = "SAJ Solar Inverter"
        self._pending_username: str = ""
        self._pending_password: str = ""

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import a config entry from configuration.yaml (sensor platform)."""
        _LOGGER.warning(
            "Importing SAJ from YAML is deprecated and will be removed; %s",
            import_config,
        )
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
            # Combine data from both steps
            combined_input = {
                CONF_HOST: self._host,
                CONF_TYPE: self._connection_type,
                CONF_USERNAME: user_input.get(CONF_USERNAME, None),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, None),
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
        """Define the schema for device credentials step."""
        return vol.Schema(
            {
                vol.Optional(CONF_NAME, default=self._pending_entry_name): str,
                vol.Optional(CONF_USERNAME, default=self._pending_username): str,
                vol.Optional(CONF_PASSWORD, default=self._pending_password): str,
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

        # Validate device
        mac_unique_id = macaddress.replace(":", "").upper() if macaddress else None
        if not mac_unique_id:
            return self.async_abort(reason="no_unique_id")

        discovered_serial: str | None = None
        title: str | None = None
        connection_type = CONNECTION_TYPES[0]  # Default to ethernet

        # If we have a MAC, check if we already have this device configured
        if macaddress:
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
            discovered_serial, title = await _validate_saj_device(
                host, CONNECTION_TYPES[0]
            )
            connection_type = CONNECTION_TYPES[0]  # Ethernet
            _LOGGER.info(
                "Successfully validated SAJ ethernet device at %s (serial=%s)",
                host,
                discovered_serial or "none",
            )
        except CannotConnect:
            # Ethernet failed — try WiFi only when hostname or MAC matches manifest
            # (e.g. hostname-only DHCP matchers for WiFi devices with a non-SAJ OUI).
            if not _dhcp_should_try_wifi_after_ethernet_fails(hostname, macaddress):
                _LOGGER.debug(
                    "Ethernet validation failed for %s and DHCP hints do not match SAJ "
                    "(hostname=%r); skipping WiFi probe",
                    host,
                    hostname,
                )
                return self.async_abort(reason="not_saj_device")
            _LOGGER.debug(
                "Ethernet validation failed for %s, trying WiFi (hostname=%r)",
                host,
                hostname,
            )
            try:
                discovered_serial, title = await _validate_saj_device(
                    host,
                    CONNECTION_TYPES[1],
                    accept_wifi_auth_challenge=True,
                )
                connection_type = CONNECTION_TYPES[1]  # WiFi
                _LOGGER.info(
                    "Successfully validated SAJ WiFi device at %s (serial=%s)",
                    host,
                    discovered_serial or "none",
                )
            except CannotConnect:
                _LOGGER.debug(
                    "Both ethernet and WiFi validation failed for %s",
                    host,
                )
                return self.async_abort(reason="not_saj_device")

        await self.async_set_unique_id(mac_unique_id, raise_on_progress=False)

        # Check if entry exists - if IP changed, update it
        existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, mac_unique_id
        )
        if existing_entry:
            current_ip = existing_entry.data.get(CONF_HOST)
            if current_ip != host:
                _LOGGER.info(
                    "Updating IP address for SAJ device %s from %s to %s",
                    mac_unique_id,
                    current_ip,
                    host,
                )
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
            else:
                _LOGGER.debug(
                    "SAJ device %s already configured with IP %s",
                    mac_unique_id,
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
        """Confirm discovered SAJ inverter.

        Credentials are not collected here.
        WiFi-only devices that need a login complete setup via reauthentication.
        """
        if user_input is not None:
            return self.async_create_entry(
                title=self.context.get("title_placeholders", {}).get(
                    "device", "SAJ Solar Inverter"
                ),
                data=self.discovery_info,
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={
                "device": self.context.get("title_placeholders", {}).get(
                    "device", "SAJ Inverter"
                ),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication (e.g. WiFi credentials after discovery)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update credentials for an existing config entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            validate_input = {
                CONF_HOST: reauth_entry.data[CONF_HOST],
                CONF_TYPE: reauth_entry.data[CONF_TYPE],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }
            try:
                await self._async_validate_input(validate_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Error reauthenticating SAJ device")
                errors["base"] = "unknown"
            else:
                data = _config_entry_data(validate_input)
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_USERNAME: data[CONF_USERNAME],
                        CONF_PASSWORD: data[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_USERNAME,
                        default=reauth_entry.data.get(CONF_USERNAME) or "",
                    ): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            description_placeholders={"name": reauth_entry.title or "SAJ"},
            errors=errors or None,
        )
