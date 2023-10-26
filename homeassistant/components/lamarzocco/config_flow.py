"""Config flow for La Marzocco integration."""
from collections.abc import Mapping
import logging
from typing import Any

from lmcloud.exceptions import AuthFail, RequestNotSuccessful
import voluptuous as vol  # type: ignore[import]

from homeassistant import config_entries, core, exceptions
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_MACHINE,
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_PORT_LOCAL,
    DOMAIN,
    SERIAL_NUMBER,
)
from .lm_client import LaMarzoccoClient

_LOGGER = logging.getLogger(__name__)

LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)

STEP_MACHINE_SELECTION_SCHEMA: vol.Schema

STEP_REAUTH_DATA_SCHEMA = LOGIN_DATA_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID, default=DEFAULT_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET, default=DEFAULT_CLIENT_SECRET): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


async def get_machines(hass: core.HomeAssistant, data: dict[str, Any]) -> list[str]:
    """Validate the user input allows us to connect."""

    try:
        lm = LaMarzoccoClient(hass, data)
        machines = await lm.get_all_machines(data)

        if not machines:
            raise CannotConnect

    except AuthFail:
        _LOGGER.error("Server rejected login credentials")
        raise InvalidAuth
    except RequestNotSuccessful:
        _LOGGER.error("Failed to connect to server")
        raise CannotConnect

    available_machines = [f"{machine[0]} ({machine[1]})" for machine in machines]

    return available_machines


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    VERSION = 1

    def __init__(self) -> None:
        """Init config flow."""
        self._discovered: dict[str, str] = {}
        self.reauth_entry: ConfigEntry | None
        self._config: dict[str, Any] = {}
        self._machines: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input is not None:
            data = user_input.copy()
            data |= self._discovered
            data[CONF_PORT] = DEFAULT_PORT_LOCAL
            data[CONF_CLIENT_ID] = DEFAULT_CLIENT_ID
            data[CONF_CLIENT_SECRET] = DEFAULT_CLIENT_SECRET

            try:
                self._machines = await get_machines(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                self._config = data
                return await self.async_step_machine_selection()

        return self.async_show_form(
            step_id="user", data_schema=LOGIN_DATA_SCHEMA, errors=errors
        )

    async def async_step_machine_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let user select machine to connect to."""
        errors = {}
        if user_input is not None:
            machine_name, serial_number = user_input[CONF_MACHINE].split(" ")
            serial_number = serial_number.strip("()")
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()
            self._config[SERIAL_NUMBER] = serial_number

            # if host is set, check if we can connect to it
            if user_input.get(CONF_HOST):
                lm = LaMarzoccoClient(self.hass, self._config)
                if not await lm.check_local_connection(
                    credentials=self._config,
                    host=user_input[CONF_HOST],
                    serial=serial_number,
                ):
                    errors[CONF_HOST] = "cannot_connect"
            if not errors:
                return self.async_create_entry(
                    title=machine_name, data=self._config | user_input
                )

        machine_selection_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MACHINE,
                    default=self._machines[0],
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=self._machines,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_MACHINE,
                    )
                ),
                vol.Optional(CONF_HOST): cv.string,
            }
        )

        return self.async_show_form(
            step_id="machine_selection",
            data_schema=machine_selection_schema,
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by discovery over Bluetooth."""
        address = discovery_info.address
        name = discovery_info.name

        _LOGGER.debug(
            "Discovered La Marzocco machine %s through Bluetooth at address %s",
            name,
            address,
        )

        self._discovered[CONF_NAME] = name
        self._discovered[CONF_MAC] = address

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        assert self.reauth_entry
        if user_input is not None:
            try:
                await get_machines(self.hass, self.reauth_entry.data | user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
