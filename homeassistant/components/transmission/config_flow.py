"""Config flow for Transmission Bittorent Client."""
import transmissionrpc
from transmissionrpc.error import TransmissionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import (
    CONF_SENSOR_TYPES,
    CONF_TURTLE_MODE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class TransmissionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UniFi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TransmissionOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Transmission flow."""
        self.config = None
        self.errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="one_instance_allowed")

        if user_input is not None:
            valid = await self.is_valid(user_input)
            if valid:
                self.config = user_input
                return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=self.errors,
        )

    async def is_valid(self, user_input):
        """Validate connection to the Transmission Client."""
        try:
            transmissionrpc.Client(
                user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                user=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )
            return True

        except TransmissionError as error:
            if str(error).find("401: Unauthorized"):
                self.errors["base"] = "cannot_connect"

        return False

    async def async_step_options(self, user_input=None):
        """Set options for the Transmission Client."""
        if user_input is not None:
            self.config["options"] = user_input
            return self.async_create_entry(
                title=self.config[CONF_NAME], data=self.config
            )

        options = {
            vol.Optional(CONF_TURTLE_MODE, default=False): bool,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        }
        for sensor in CONF_SENSOR_TYPES:
            options.update(
                {vol.Optional(sensor, default=CONF_SENSOR_TYPES[sensor][2]): bool}
            )

        return self.async_show_form(step_id="options", data_schema=vol.Schema(options))

    async def async_step_import(self, import_config):
        """Import from Transmission client config."""
        config = {
            CONF_NAME: import_config.get(CONF_NAME, DEFAULT_NAME),
            CONF_HOST: import_config[CONF_HOST],
            CONF_USERNAME: import_config.get(CONF_USERNAME),
            CONF_PASSWORD: import_config.get(CONF_PASSWORD),
            CONF_PORT: import_config.get(CONF_PORT, DEFAULT_PORT),
        }

        return await self.async_step_user(user_input=config)


class TransmissionOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry):
        """Initialize Transmission options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Transmission options."""
        if user_input is not None:
            options = {}
            options[CONF_MONITORED_CONDITIONS] = {}
            for sensor in CONF_SENSOR_TYPES:
                options[CONF_MONITORED_CONDITIONS][sensor] = user_input[sensor]
            options[CONF_TURTLE_MODE] = user_input[CONF_TURTLE_MODE]
            options[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]

            return self.async_create_entry(title="", data=options)

        options = {
            vol.Optional(
                CONF_TURTLE_MODE,
                default=self.config_entry.options.get(
                    CONF_TURTLE_MODE,
                    self.config_entry.data["options"][CONF_TURTLE_MODE],
                ),
            ): bool,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL,
                    self.config_entry.data["options"][CONF_SCAN_INTERVAL],
                ),
            ): int,
        }
        for sensor in CONF_SENSOR_TYPES:
            options.update(
                {
                    vol.Optional(
                        sensor,
                        default=self.config_entry.options[
                            CONF_MONITORED_CONDITIONS
                        ].get(sensor, self.config_entry.data["options"][sensor]),
                    ): bool
                }
            )
        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
