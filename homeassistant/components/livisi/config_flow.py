"""Config flow for Livisi Home Assistant."""

from collections.abc import Mapping
from typing import Any, override

from livisi import (
    IncorrectIpAddressException,
    LivisiConnection,
    LivisiController,
    LivisiException,
    ShcUnreachableException,
    WrongCredentialException,
    connect as livisi_connect,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from .const import DOMAIN, LOGGER


class LivisiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Livisi Smart Home config flow."""

    def __init__(self) -> None:
        """Create the configuration file."""
        self.aio_livisi: LivisiConnection | None = None
        self.data_schema = probatio.Schema(
            {
                probatio.Required(CONF_HOST): str,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
            }
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.data_schema)

        errors = {}
        try:
            await self._login(user_input)
        except WrongCredentialException:
            errors["base"] = "wrong_password"
        except ShcUnreachableException:
            errors["base"] = "cannot_connect"
        except IncorrectIpAddressException:
            errors["base"] = "wrong_ip_address"
        except LivisiException:
            errors["base"] = "cannot_connect"
        else:
            assert self.aio_livisi is not None
            try:
                if controller := self.aio_livisi.controller:
                    return await self.create_entity(user_input, controller)
                errors["base"] = "cannot_connect"
            finally:
                await self.aio_livisi.close()

        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        errors = {}
        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            try:
                connection = await livisi_connect(
                    reauth_entry.data[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except WrongCredentialException:
                errors["base"] = "wrong_password"
            except IncorrectIpAddressException:
                errors["base"] = "wrong_ip_address"
            except LivisiException:
                errors["base"] = "cannot_connect"
            else:
                controller = connection.controller
                await connection.close()
                if controller:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                    )
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            errors=errors,
        )

    async def _login(self, user_input: dict[str, str]) -> None:
        """Login into Livisi Smart Home."""
        self.aio_livisi = await livisi_connect(
            user_input[CONF_HOST], user_input[CONF_PASSWORD]
        )

    async def create_entity(
        self, user_input: dict[str, str], controller: LivisiController
    ) -> ConfigFlowResult:
        """Create LIVISI entity."""
        LOGGER.debug(
            "Integrating SHC %s with serial number: %s",
            controller.controller_type,
            controller.serial_number,
        )

        return self.async_create_entry(
            title=f"SHC {controller.controller_type}",
            data={
                **user_input,
            },
        )
