"""Config flow for La Marzocco integration."""
from collections.abc import Mapping
import logging
from typing import Any

from lmcloud.exceptions import AuthFail, RequestNotSuccessful
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_MACHINE, DOMAIN
from .lm_client import LaMarzoccoClient

_LOGGER = logging.getLogger(__name__)

LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


async def get_machines(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> list[tuple[str, str]]:
    """Validate the user input allows us to connect."""

    try:
        lm = LaMarzoccoClient(hass=hass)
        machines = await lm.get_all_machines(data)

    except AuthFail:
        _LOGGER.error("Server rejected login credentials")
        raise InvalidAuth
    except RequestNotSuccessful:
        _LOGGER.error("Failed to connect to server")
        raise CannotConnect

    if not machines:
        raise NoMachines

    return machines


class LmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    VERSION = 1

    def __init__(self) -> None:
        """Init config flow."""
        self._discovered: dict[str, str] = {}
        self.reauth_entry: ConfigEntry | None
        self._config: dict[str, Any] = {}
        self._machines: list[tuple[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input:
            data = {
                **user_input,
                **self._discovered,
            }

            try:
                self._machines = await get_machines(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NoMachines:
                errors["base"] = "no_machines"

            if not errors:
                if self._discovered:
                    serials = [machine[0] for machine in self._machines]
                    if self._discovered[CONF_MACHINE] not in serials:
                        errors["base"] = "machine_not_found"
                    else:
                        self._config = data
                        return await self.async_step_host_selection()

            if not errors:
                self._config = data
                return await self.async_step_machine_selection()

        return self.async_show_form(
            step_id="user", data_schema=LOGIN_DATA_SCHEMA, errors=errors
        )

    async def async_validate_host(
        self, serial_number: str, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Validate the host input."""
        errors: dict[str, str] = {}
        # if host is set, check if we can connect to it
        if user_input.get(CONF_HOST):
            lm = LaMarzoccoClient(hass=self.hass)
            if not await lm.check_local_connection(
                credentials=self._config,
                host=user_input[CONF_HOST],
                serial=serial_number,
            ):
                errors[CONF_HOST] = "cannot_connect"
        return errors

    async def async_step_host_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Machine was discovered, only enter host."""
        errors: dict[str, str] = {}
        serial_number = self._discovered[CONF_MACHINE]
        if user_input:
            errors = await self.async_validate_host(serial_number, user_input)
            if not errors:
                return self.async_create_entry(
                    title=serial_number,
                    data=self._config | user_input,
                )
        return self.async_show_form(
            step_id="host_selection",
            data_schema=vol.Schema({vol.Optional(CONF_HOST): cv.string}),
            errors=errors,
        )

    async def async_step_machine_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let user select machine to connect to."""
        errors: dict[str, str] = {}
        if user_input:
            serial_number = user_input[CONF_MACHINE]
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()

            errors = await self.async_validate_host(serial_number, user_input)

            if not errors:
                return self.async_create_entry(
                    title=serial_number,
                    data=self._config | user_input,
                )

        machine_options = [
            SelectOptionDict(
                value=serial_number,
                label=f"{model_name} ({serial_number})",
            )
            for serial_number, model_name in self._machines
        ]
        machine_selection_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MACHINE,
                    default=machine_options[0],
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=machine_options,
                        mode=SelectSelectorMode.DROPDOWN,
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

        serial = name.split("_")[1]
        self._discovered[CONF_MACHINE] = serial

        await self.async_set_unique_id(serial)
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
            except NoMachines:
                errors["base"] = "no_machines"
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=LOGIN_DATA_SCHEMA,
            errors=errors,
        )


class NoMachines(exceptions.HomeAssistantError):
    """Error to indicate we couldn't find machines."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
