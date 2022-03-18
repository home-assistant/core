"""Config flow to configure the Venstar integration."""
from venstarcolortouch import VenstarColorTouch
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
)

from .const import _LOGGER, DOMAIN, VENSTAR_TIMEOUT

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_PIN): str,
        vol.Optional(CONF_SSL, default=False): bool,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
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

    return {"title": client.name}


class VenstarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a venstar config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create config entry. Show the setup form to the user."""
        errors = {}
        info = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data):
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
