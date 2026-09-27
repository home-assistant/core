"""Config flow to configure the Venstar integration."""

from typing import Any, override

import probatio
from venstarcolortouch import VenstarColorTouch

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER, VENSTAR_TIMEOUT


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect."""
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    pin = data.get(CONF_PIN)
    host = data[CONF_HOST]
    timeout = VENSTAR_TIMEOUT
    protocol = "https" if data[CONF_SSL] else "http"

    client = VenstarColorTouch(
        addr=host,
        timeout=timeout,
        user=username,
        password=password,
        pin=pin,
        proto=protocol,
    )

    # perform a full info pull, because this calls login also.

    info_success = await hass.async_add_executor_job(client.update_info)
    if not info_success:
        raise CannotConnect

    return client.name


class VenstarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a venstar config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create config entry. Show the setup form to the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                title = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST): str,
                    probatio.Optional(CONF_USERNAME): str,
                    probatio.Optional(CONF_PASSWORD): str,
                    probatio.Optional(CONF_PIN): str,
                    probatio.Optional(CONF_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import entry from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        return await self.async_step_user(
            {
                CONF_HOST: import_data[CONF_HOST],
                CONF_USERNAME: import_data.get(CONF_USERNAME),
                CONF_PASSWORD: import_data.get(CONF_PASSWORD),
                CONF_PIN: import_data.get(CONF_PIN),
                CONF_SSL: import_data[CONF_SSL],
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
