"""Config flow for La Marzocco integration."""
from collections.abc import Mapping
import logging
from typing import Any

from lmcloud import LMCloud as LaMarzoccoClient
from lmcloud.exceptions import AuthFail, RequestNotSuccessful
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_MACHINE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    def __init__(self) -> None:
        """Initialize the config flow."""

        self.reauth_entry: ConfigEntry | None = None
        self._config: dict[str, Any] = {}
        self._machines: list[tuple[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input:
            data: dict[str, Any] = {}
            if self.reauth_entry:
                data = dict(self.reauth_entry.data)
            data = {
                **data,
                **user_input,
            }

            lm = LaMarzoccoClient()
            try:
                self._machines = await lm.get_all_machines(data)
            except AuthFail:
                _LOGGER.debug("Server rejected login credentials")
                errors["base"] = "invalid_auth"
            except RequestNotSuccessful as exc:
                _LOGGER.error("Error connecting to server: %s", exc)
                errors["base"] = "cannot_connect"
            else:
                if not self._machines:
                    errors["base"] = "no_machines"

            if not errors:
                if self.reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=data
                    )
                    await self.hass.config_entries.async_reload(
                        self.reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

            if not errors:
                self._config = data
                return await self.async_step_machine_selection()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
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

            # validate local connection if host is provided
            if user_input.get(CONF_HOST):
                lm = LaMarzoccoClient()
                if not await lm.check_local_connection(
                    credentials=self._config,
                    host=user_input[CONF_HOST],
                    serial=serial_number,
                ):
                    errors[CONF_HOST] = "cannot_connect"

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
                    CONF_MACHINE, default=machine_options[0]["value"]
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
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        return await self.async_step_user(user_input)
