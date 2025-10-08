"""Config flow for Netgear LTE integration."""

from __future__ import annotations

from typing import Any

from aiohttp.cookiejar import CookieJar
from eternalegypt import Error, Modem
from eternalegypt.eternalegypt import Information
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DEFAULT_HOST, DOMAIN, LOGGER, MANUFACTURER


class NetgearLTEFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Netgear LTE."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input:
            host = user_input[CONF_HOST]
            password = user_input[CONF_PASSWORD]

            try:
                info = await self._async_validate_input(host, password)
            except InputValidationError as ex:
                errors["base"] = ex.base
            else:
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{MANUFACTURER} {info.items['general.devicename']}",
                    data={CONF_HOST: host, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                user_input or {CONF_HOST: DEFAULT_HOST},
            ),
            errors=errors,
        )

    async def _async_validate_input(self, host: str, password: str) -> Information:
        """Validate login credentials."""
        websession = async_create_clientsession(
            self.hass, cookie_jar=CookieJar(unsafe=True)
        )

        modem = Modem(
            hostname=host,
            password=password,
            websession=websession,
        )
        try:
            await modem.login()
            info = await modem.information()
        except Error as ex:
            raise InputValidationError("cannot_connect") from ex
        except Exception as ex:
            LOGGER.exception("Unexpected exception")
            raise InputValidationError("unknown") from ex
        await modem.logout()
        return info


class InputValidationError(HomeAssistantError):
    """Error to indicate we cannot proceed due to invalid input."""

    def __init__(self, base: str) -> None:
        """Initialize with error base."""
        super().__init__()
        self.base = base
