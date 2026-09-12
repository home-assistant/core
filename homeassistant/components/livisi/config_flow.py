"""Config flow for Livisi Home Assistant."""

from typing import override

from livisi import (
    IncorrectIpAddressException,
    LivisiConnection,
    LivisiController,
    LivisiException,
    ShcUnreachableException,
    WrongCredentialException,
    connect as livisi_connect,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from .const import DOMAIN, LOGGER


class LivisiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Livisi Smart Home config flow."""

    def __init__(self) -> None:
        """Create the configuration file."""
        self.aio_livisi: LivisiConnection | None = None
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PASSWORD): str,
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
