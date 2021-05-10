"""Config flow to configure onkyo component."""
import logging
from urllib.parse import urlparse

from eiscp import eISCP as onkyo_rcv
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.persistent_notification import create as notify_create
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import default_sources
from .const import (
    CONF_MAX_VOLUME,
    CONF_RECEIVER_MAX_VOLUME,
    CONF_SOURCES,
    DEFAULT_NAME,
    DEFAULT_RECEIVER_MAX_VOLUME,
    DEFAULT_SOURCES_SELECTED,
    SUPPORTED_MAX_VOLUME,
    UNKNOWN_MODEL,
)
from .const import DOMAIN  # pylint:disable=unused-import

DEFAULT_SOURCES = default_sources()

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MAX_VOLUME, default=SUPPORTED_MAX_VOLUME): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(
            CONF_RECEIVER_MAX_VOLUME, default=DEFAULT_RECEIVER_MAX_VOLUME
        ): cv.positive_int,
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES_SELECTED): cv.multi_select(
            DEFAULT_SOURCES
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


class OnkyoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Onkyo configuration flow."""

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
            host = user_input[CONF_HOST]
            try:
                receiver = onkyo_rcv(host)
                if receiver.model_name == UNKNOWN_MODEL:
                    errors["base"] = "receiver_unknown"
            except OSError as error:
                _LOGGER.error("Unable to connect to receiver at %s (%s)", host, error)
                errors["base"] = "cannot_connect"

            if "base" not in errors:
                await self.async_set_unique_id(receiver.identifier)
                self._abort_if_unique_id_configured()
                if self.is_imported:
                    notify_create(
                        self.hass,
                        "The import of the Onkyo configuration was successful. \
                        Please remove the platform from the YAML configuration file",
                        "Onkyo Import",
                    )

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered device."""
        user_input = {
            CONF_HOST: urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname,
            CONF_NAME: discovery_info["friendlyName"],
        }
        return await self.async_step_user(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self._other_options = None

    async def async_step_init(self, user_input=None):
        """Select sources."""
        errors = {}
        select_sources = []
        if user_input is not None:
            if user_input.get(CONF_SOURCES):
                sources_selected = user_input.pop(CONF_SOURCES)
                self._other_options = user_input
                return await self.async_step_customize(
                    sources_selected=sources_selected
                )
            return self.async_create_entry(title="", data={CONF_SOURCES: {}})

        if self.config_entry.options.get(CONF_SOURCES):
            for key, value in self.config_entry.options[CONF_SOURCES].items():
                DEFAULT_SOURCES[key] = value
            select_sources = list(self.config_entry.options[CONF_SOURCES].keys())

        supported_max_volume = self.config_entry.options.get(
            CONF_MAX_VOLUME, SUPPORTED_MAX_VOLUME
        )
        default_receiver_max_volume = self.config_entry.options.get(
            CONF_RECEIVER_MAX_VOLUME, DEFAULT_RECEIVER_MAX_VOLUME
        )
        sources_schema = vol.Schema(
            {
                vol.Optional(CONF_MAX_VOLUME, default=supported_max_volume): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
                vol.Optional(
                    CONF_RECEIVER_MAX_VOLUME, default=default_receiver_max_volume
                ): cv.positive_int,
                vol.Required(CONF_SOURCES, default=select_sources): cv.multi_select(
                    DEFAULT_SOURCES
                ),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=sources_schema, errors=errors
        )

    async def async_step_customize(self, user_input=None, sources_selected=None):
        """Rename sources."""
        if user_input is not None:
            data = {CONF_SOURCES: user_input}
            data.update(self._other_options)
            return self.async_create_entry(title="", data=data)
        data_schema = rename_sources(sources_selected)
        return self.async_show_form(step_id="customize", data_schema=data_schema)


def rename_sources(sources) -> vol.Schema:
    """Prepare schema."""
    rename_schema = {}
    for source in sources:
        rename_schema.update(
            {
                vol.Required(
                    source, default=DEFAULT_SOURCES.get(source, source)
                ): cv.string
            }
        )
    return vol.Schema(rename_schema)
