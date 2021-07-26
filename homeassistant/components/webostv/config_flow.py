"""Config flow to configure webostv component."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from aiopylgtv import PyLGTVPairException
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from . import async_control_connect
from .const import CONF_SOURCES, DEFAULT_NAME, DOMAIN, WEBOSTV_EXCEPTIONS

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """WebosTV configuration flow."""

    VERSION = 1

    def __init__(self):
        """Initialize workflow."""
        self._host = None
        self._name = None
        self._uuid = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        self._host = import_info[CONF_HOST]
        self._name = import_info.get(CONF_NAME) or import_info[CONF_HOST]
        return await self.async_step_pairing()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]
            return await self.async_step_pairing()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @callback
    def _async_check_configured_entry(self):
        """Check if entry is configured, update unique_id if needed."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] != self._host:
                continue

            if self._uuid and not entry.unique_id:
                _LOGGER.debug(
                    "Updating unique_id for host %s, unique_id: %s",
                    self._host,
                    self._uuid,
                )
                self.hass.config_entries.async_update_entry(entry, unique_id=self._uuid)

            raise data_entry_flow.AbortFlow("already_configured")

    async def async_step_pairing(self, user_input=None):
        """Display pairing form."""
        self._async_check_configured_entry()

        self.context[CONF_HOST] = self._host
        self.context["title_placeholders"] = {"name": self._name}
        errors = {}

        if (
            self.context["source"] == config_entries.SOURCE_IMPORT
            or user_input is not None
        ):
            try:
                client = await async_control_connect(self._host, None)
            except PyLGTVPairException:
                return self.async_abort(reason="error_pairing")
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                data = {CONF_HOST: self._host, CONF_CLIENT_SECRET: client.client_key}
                return self.async_create_entry(title=self._name, data=data)

        return self.async_show_form(step_id="pairing", errors=errors)

    async def async_step_ssdp(self, discovery_info):
        """Handle a flow initialized by discovery."""
        self._host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        self._name = discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]

        uuid = discovery_info[ssdp.ATTR_UPNP_UDN]
        if uuid.startswith("uuid:"):
            uuid = uuid[5:]
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured({CONF_HOST: self._host})

        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self._host:
                return self.async_abort(reason="already_in_progress")

        self._uuid = uuid
        return await self.async_step_pairing()


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
            options_input = {CONF_SOURCES: user_input[CONF_SOURCES]}
            return self.async_create_entry(title="", data=options_input)
        # Get sources
        sources = self.options.get(CONF_SOURCES, "")
        sources_list = await async_get_sources(self.host, self.key)
        if sources_list is None:
            errors["base"] = "cannot_retrieve"

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SOURCES,
                    description={"suggested_value": sources},
                ): cv.multi_select(sources_list),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )


async def async_get_sources(host, key):
    """Construct sources list."""
    try:
        client = await async_control_connect(host, key)
    except WEBOSTV_EXCEPTIONS:
        return None

    return [
        *(app["title"] for app in client.apps.values()),
        *(app["label"] for app in client.inputs.values()),
    ]
