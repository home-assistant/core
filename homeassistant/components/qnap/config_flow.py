"""Config flow to configure qnap component."""
import logging

from qnapstats import QNAPStats
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.persistent_notification import create as notify_create
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    _MONITORED_CONDITIONS,
    CONF_DRIVES,
    CONF_NICS,
    CONF_VOLUMES,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
)
from .const import DOMAIN  # pylint:disable=unused-import

NICS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NICS): cv.string,
    }
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): cv.multi_select(
            _MONITORED_CONDITIONS
        ),
        vol.Optional(CONF_NICS): cv.string,
        vol.Optional(CONF_DRIVES): cv.string,
        vol.Optional(CONF_VOLUMES): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


class QnapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Qnap configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize."""
        self.is_imported = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        self.is_imported = True
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            host = user_input.get(CONF_HOST)
            protocol = "https" if user_input.get(CONF_SSL, False) else "http"
            api = QNAPStats(
                host=f"{protocol}://{host}",
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
                timeout=user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            )
            try:
                stats = await self.hass.async_add_executor_job(api.get_system_stats)
            except Exception:  # noqa: E722 pylint: disable=broad-except
                _LOGGER.error("Failed to fetch QNAP stats from the NAS (%s)", host)
                errors["base"] = "cannot_connect"

            if "base" not in errors:
                unique_id = stats.get("system", {}).get("serial_number", host)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = stats.get("system", {}).get("name", host).capitalize()
                if self.is_imported:
                    notify_create(
                        self.hass,
                        "The import of the QNAP configuration was successful. \
                        Please remove the platform from the YAML configuration file",
                        "QNAP Import",
                    )
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = config_entry.options

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            user_input[CONF_NICS] = cv.ensure_list(user_input.get(CONF_NICS))
            user_input[CONF_DRIVES] = cv.ensure_list(user_input.get(CONF_DRIVES))
            user_input[CONF_VOLUMES] = cv.ensure_list(user_input.get(CONF_VOLUMES))
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SSL,
                    default=self.options.get(CONF_SSL, False),
                ): cv.boolean,
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=self.options.get(CONF_VERIFY_SSL, True),
                ): cv.boolean,
                vol.Optional(
                    CONF_TIMEOUT,
                    default=self.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): cv.positive_int,
                vol.Optional(
                    CONF_MONITORED_CONDITIONS,
                    default=self.options.get(CONF_MONITORED_CONDITIONS, []),
                ): cv.multi_select(_MONITORED_CONDITIONS),
                vol.Optional(
                    CONF_NICS,
                    description={
                        "suggested_value": ",".join(self.options.get(CONF_NICS, []))
                    },
                ): cv.string,
                vol.Optional(
                    CONF_DRIVES,
                    description={
                        "suggested_value": ",".join(self.options.get(CONF_DRIVES, []))
                    },
                ): cv.string,
                vol.Optional(
                    CONF_VOLUMES,
                    description={
                        "suggested_value": ",".join(self.options.get(CONF_VOLUMES, []))
                    },
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
