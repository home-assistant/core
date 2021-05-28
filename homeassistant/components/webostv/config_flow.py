"""Config flow to configure webostv component."""
import logging
from urllib.parse import urlparse

from aiopylgtv import PyLGTVPairException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from . import CannotConnect, async_control_connect
from .const import CONF_ON_ACTION, CONF_SOURCES, DEFAULT_NAME, DEFAULT_SOURCES, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

DOCS_URL = "https://www.home-assistant.io/integrations/webostv"

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """WebosTV configuration flow."""

    VERSION = 1

    def __init__(self):
        """Initialize workflow."""
        self._user_input = {}
        self._force_pairing = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        self._force_pairing = True
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._user_input = user_input
            self.context["title_placeholders"] = {
                "name": user_input.get(CONF_NAME, CONF_HOST)
            }
            if self._force_pairing:
                return await self.async_step_pairing({})

            return await self.async_step_pairing()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_pairing(self, user_input=None):
        """Display pairing form."""
        errors = {}
        if user_input is not None:
            try:
                client = await async_control_connect(
                    self.hass, self._user_input[CONF_HOST], None
                )
            except PyLGTVPairException:
                return self.async_abort(reason="error_pairing")
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_register(self._user_input, client)

        return self.async_show_form(
            step_id="pairing",
            errors=errors,
        )

    async def async_step_register(self, user_input, client=None):
        """Register entity."""
        if client.is_registered():
            if client.client_key is None:
                self.async_abort(reason="client_key_notfound")

            await self.async_set_unique_id(client.software_info["device_id"])
            self._abort_if_unique_id_configured()

            data = {
                CONF_HOST: self._user_input[CONF_HOST],
                CONF_NAME: self._user_input[CONF_NAME],
                CONF_CLIENT_SECRET: client.client_key,
            }
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, CONF_HOST), data=data
            )

        return await self.async_step_user()

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Webostv device."""
        user_input = {
            CONF_HOST: urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname,
            CONF_NAME: discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME],
        }
        self.context["title_placeholders"] = {"name": user_input[CONF_NAME]}
        self._force_pairing = True
        return await self.async_step_user(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = config_entry.options
        self.host = config_entry.data[CONF_HOST]
        self.key = config_entry.data[CONF_CLIENT_SECRET]

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_ON_ACTION) and not self.hass.states.get(
                user_input.get(CONF_ON_ACTION)
            ):
                errors["base"] = "script_notfound"
            elif (
                user_input.get(CONF_ON_ACTION)
                and (self.hass.states.get(user_input.get(CONF_ON_ACTION))).domain
                != "script"
            ):
                errors["base"] = "script_notfound"
            if "base" not in errors:
                options_input = {
                    CONF_ON_ACTION: user_input.get(CONF_ON_ACTION),
                    CONF_SOURCES: user_input[CONF_SOURCES],
                }
                return self.async_create_entry(title="", data=options_input)

        # Get turn on service
        script_turn_on = self.options.get(CONF_ON_ACTION, "")

        # Get sources
        sources = self.options.get(CONF_SOURCES, DEFAULT_SOURCES)
        sources_list = await async_default_sources(self.hass, self.host, self.key)
        if sources_list is None:
            errors["base"] = "cannot_retrieve"
            sources_list = self.options.get(CONF_SOURCES, DEFAULT_SOURCES)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ON_ACTION,
                    description={"suggested_value": script_turn_on},
                ): str,
                vol.Optional(
                    CONF_SOURCES,
                    description={"suggested_value": sources},
                ): cv.multi_select(sources_list),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={"docs_url": DOCS_URL},
        )


async def async_default_sources(hass, host, key) -> list:
    """Construct sources list."""
    sources = []
    try:
        client = await async_control_connect(hass, host, key)
    except CannotConnect as error:
        _LOGGER.warning("Unable to retrieve.Device must be switched off (%s)", error)
        return None

    for app in client.apps.values():
        sources.append(app["title"])
    for source in client.inputs.values():
        sources.append(source["label"])

    return sources
