"""Config flow for the Airobot integration."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any, override

from modbus_connection import ModbusTcpParams
import probatio
from pyairobotmodbus import DEFAULT_PORT, DEFAULT_UNIT_ID, AirobotModbusClient
from pyairobotmodbus.exceptions import AirobotError as VUError, AirobotReadError
from pyairobotmodbus.models import AirobotIdentity
from pyairobotrest import AirobotClient
from pyairobotrest.exceptions import (
    AirobotAuthError,
    AirobotConnectionError,
    AirobotError,
    AirobotTimeoutError,
)

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow as BaseConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_THERMOSTAT,
    DEVICE_TYPE_VENTILATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_THERMOSTAT_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

STEP_VENTILATION_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
    }
)


@dataclass
class DeviceInfo:
    """Device information."""

    title: str
    device_id: str


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> DeviceInfo:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_THERMOSTAT_DATA_SCHEMA with values provided by the user.
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
        status, settings = await asyncio.gather(
            client.get_statuses(), client.get_settings()
        )
    except AirobotAuthError as err:
        raise InvalidAuth from err
    except (
        AirobotConnectionError,
        AirobotTimeoutError,
        AirobotError,
        TimeoutError,
    ) as err:
        raise CannotConnect from err

    # Use device name or device ID as title
    title = settings.device_name or status.device_id

    return DeviceInfo(title=title, device_id=status.device_id)


async def validate_ventilation_input(
    hass: HomeAssistant, data: dict[str, Any]
) -> AirobotIdentity | None:
    """Validate the ventilation unit connection and read its identity.

    Returns None for firmware without the identity registers.
    """
    params = ModbusTcpParams(host=data[CONF_HOST], port=DEFAULT_PORT)
    try:
        async with async_get_temporary_unit(hass, params, DEFAULT_UNIT_ID) as unit:
            client = AirobotModbusClient(unit)
            await client.async_get_data()
            try:
                return await client.async_get_identity()
            except AirobotReadError:
                return None
    except (VUError, HomeAssistantError) as err:
        raise CannotConnect from err


class AirobotConfigFlow(BaseConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airobot."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_mac: str | None = None
        self._discovered_device_id: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - show menu to choose device type."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["thermostat", "ventilation"],
        )

    async def async_step_thermostat(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle thermostat setup."""
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
                return self.async_create_entry(
                    title=info.title,
                    data={
                        **user_input,
                        CONF_DEVICE_TYPE: DEVICE_TYPE_THERMOSTAT,
                    },
                )

        return self.async_show_form(
            step_id="thermostat",
            data_schema=STEP_THERMOSTAT_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_ventilation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle ventilation unit setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Firmware without the identity registers leaves entries without
            # a unique ID, so match on the host as well
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
                }
            )
            try:
                identity = await validate_ventilation_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {**user_input, CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION}
                if identity is not None:
                    mac = format_mac(identity.mac_address)
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: user_input[CONF_HOST]}
                    )
                    data[CONF_MAC] = mac
                return self.async_create_entry(title="Airobot Ventilation", data=data)

        return self.async_show_form(
            step_id="ventilation",
            data_schema=STEP_VENTILATION_DATA_SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        # Store the discovered IP address and MAC
        self._discovered_host = discovery_info.ip
        self._discovered_mac = discovery_info.macaddress

        hostname = discovery_info.hostname.lower()

        if hostname == "airobot-ventilation":
            # Ventilation unit discovered
            self._discovered_mac = format_mac(discovery_info.macaddress)
            await self.async_set_unique_id(self._discovered_mac)
            self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
            # Entries added manually on firmware without the identity registers
            # have no unique ID and are keyed by host; upgrade them with the
            # discovered MAC so later IP changes are tracked like other entries
            for entry in self._async_current_entries(include_ignore=False):
                if (
                    entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_VENTILATION
                    and entry.data.get(CONF_HOST) == discovery_info.ip
                ):
                    if entry.unique_id is None:
                        self.hass.config_entries.async_update_entry(
                            entry,
                            unique_id=self._discovered_mac,
                            data={**entry.data, CONF_MAC: self._discovered_mac},
                        )
                    return self.async_abort(reason="already_configured")
            return await self.async_step_vu_dhcp_confirm()

        # Extract device_id from hostname (format: airobot-thermostat-t01xxxxxx)
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
                # Store MAC address and device type in config entry data
                if self._discovered_mac:
                    data[CONF_MAC] = self._discovered_mac
                data[CONF_DEVICE_TYPE] = DEVICE_TYPE_THERMOSTAT

                return self.async_create_entry(title=info.title, data=data)

        # Only ask for password since we already have the device_id from discovery
        return self.async_show_form(
            step_id="dhcp_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            description_placeholders={
                "host": self._discovered_host or "",
                "device_id": self._discovered_device_id or "",
            },
            errors=errors,
        )

    async def async_step_vu_dhcp_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle DHCP discovery confirmation for ventilation unit."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {CONF_HOST: self._discovered_host}

            try:
                await validate_ventilation_input(self.hass, data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                entry_data: dict[str, Any] = {
                    **data,
                    CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
                }
                if self._discovered_mac:
                    entry_data[CONF_MAC] = self._discovered_mac

                return self.async_create_entry(
                    title="Airobot Ventilation",
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="vu_dhcp_confirm",
            description_placeholders={
                "host": self._discovered_host or "",
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        reconfigure_entry = self._get_reconfigure_entry()

        if reconfigure_entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_VENTILATION:
            return await self.async_step_reconfigure_ventilation(user_input)

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
                STEP_THERMOSTAT_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_reconfigure_ventilation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration for ventilation unit."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Prevent repointing the entry at an already configured device
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
                }
            )
            try:
                identity = await validate_ventilation_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if identity is not None and reconfigure_entry.unique_id is not None:
                    await self.async_set_unique_id(format_mac(identity.mac_address))
                    self._abort_if_unique_id_mismatch(reason="wrong_ventilation_unit")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure_ventilation",
            data_schema=self.add_suggested_values_to_schema(
                STEP_VENTILATION_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon an API authentication error."""
        # Ventilation units have no credentials to reauthenticate
        if entry_data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_VENTILATION:
            return self.async_abort(reason="reauth_unsupported")
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
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
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
