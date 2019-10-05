"""Config flow to configure Samsung TV."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.components.ssdp import (
    ATTR_HOST,
    ATTR_NAME,
    ATTR_MODEL_NAME,
    ATTR_MANUFACTURER,
    ATTR_UDN,
)

from .const import CONF_MANUFACTURER, CONF_MODEL, DOMAIN


DATA_SCHEMA = vol.Schema({CONF_HOST: str, CONF_NAME: str})


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._ip = None
        self._manufacturer = None
        self._model = None
        self._uuid = None
        self._name = None
        self._title = None

    def _get_ip(self, host):
        import socket

        if host is None:
            return
        return socket.gethostbyname(host)

    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._title,
            data={
                CONF_HOST: self._host,
                CONF_IP_ADDRESS: self._ip,
                CONF_NAME: self._name,
                CONF_MANUFACTURER: self._manufacturer,
                CONF_MODEL: self._model,
                CONF_ID: self._uuid,
            },
        )

    async def async_step_user(self, user_input=None, error=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._title = user_input[CONF_NAME]
            self._ip = self._get_ip(self._host)
            return self._async_get_entry()

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        ip = self.context[CONF_IP_ADDRESS] = self._get_ip(user_input[ATTR_HOST])

        if any(
            ip == flow["context"].get(CONF_IP_ADDRESS)
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if ip == entry.data.get(CONF_IP_ADDRESS):
                return self.async_abort(reason="already_configured")

        self._host = user_input[ATTR_HOST]
        self._ip = ip
        self._manufacturer = user_input[ATTR_MANUFACTURER]
        self._model = user_input[ATTR_MODEL_NAME]
        if user_input[ATTR_UDN].startswith("uuid:"):
            self._uuid = user_input[ATTR_UDN][5:]
        else:
            self._uuid = user_input[ATTR_UDN]
        self._name = user_input[ATTR_NAME]
        if self._name.startswith("[TV]"):
            self._name = self._name[4:]
        self._title = "{} ({})".format(self._name, self._model)

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return self._async_get_entry()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"title": self._title}
        )
