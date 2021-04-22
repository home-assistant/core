"""Config flow for Samsung TV."""
import socket
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)

from .bridge import SamsungTVBridge
from .const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    DOMAIN,
    LOGGER,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    RESULT_AUTH_MISSING,
    RESULT_CANNOT_CONNECT,
    RESULT_SUCCESS,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})
SUPPORTED_METHODS = [METHOD_LEGACY, METHOD_WEBSOCKET]


def _get_ip(host):
    if host is None:
        return None
    return socket.gethostbyname(host)


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
        self._name = None
        self._title = None
        self._id = None
        self._bridge = None

    def _get_entry(self):
        data = {
            CONF_HOST: self._host,
            CONF_ID: self._id,
            CONF_IP_ADDRESS: self._ip,
            CONF_MANUFACTURER: self._manufacturer,
            CONF_METHOD: self._bridge.method,
            CONF_MODEL: self._model,
            CONF_NAME: self._name,
            CONF_PORT: self._bridge.port,
        }
        if self._bridge.token:
            data[CONF_TOKEN] = self._bridge.token
        return self.async_create_entry(
            title=self._title,
            data=data,
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        for method in SUPPORTED_METHODS:
            self._bridge = SamsungTVBridge.get_bridge(method, self._host)
            result = self._bridge.try_connect()
            if result != RESULT_CANNOT_CONNECT:
                return result
        LOGGER.debug("No working config found")
        return RESULT_CANNOT_CONNECT

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            ip_address = await self.hass.async_add_executor_job(
                _get_ip, user_input[CONF_HOST]
            )

            await self.async_set_unique_id(ip_address)
            self._abort_if_unique_id_configured()

            self._host = user_input.get(CONF_HOST)
            self._ip = self.context[CONF_IP_ADDRESS] = ip_address
            self._name = user_input.get(CONF_NAME)
            self._title = self._name

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result != RESULT_SUCCESS:
                return self.async_abort(reason=result)
            return self._get_entry()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_ssdp(self, discovery_info):
        """Handle a flow initialized by discovery."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        ip_address = await self.hass.async_add_executor_job(_get_ip, host)

        self._host = host
        self._ip = self.context[CONF_IP_ADDRESS] = ip_address
        self._manufacturer = discovery_info.get(ATTR_UPNP_MANUFACTURER)
        self._model = discovery_info.get(ATTR_UPNP_MODEL_NAME)
        self._name = f"Samsung {self._model}"
        self._id = discovery_info.get(ATTR_UPNP_UDN)
        self._title = self._model

        # probably access denied
        if self._id is None:
            return self.async_abort(reason=RESULT_AUTH_MISSING)
        if self._id.startswith("uuid:"):
            self._id = self._id[5:]

        await self.async_set_unique_id(ip_address)
        self._abort_if_unique_id_configured(
            {
                CONF_ID: self._id,
                CONF_MANUFACTURER: self._manufacturer,
                CONF_MODEL: self._model,
            }
        )

        self.context["title_placeholders"] = {"model": self._model}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            result = await self.hass.async_add_executor_job(self._try_connect)

            if result != RESULT_SUCCESS:
                return self.async_abort(reason=result)
            return self._get_entry()

        return self.async_show_form(
            step_id="confirm", description_placeholders={"model": self._model}
        )

    async def async_step_reauth(self, user_input=None):
        """Handle configuration by re-auth."""
        self._host = user_input[CONF_HOST]
        self._id = user_input.get(CONF_ID)
        self._ip = user_input[CONF_IP_ADDRESS]
        self._manufacturer = user_input.get(CONF_MANUFACTURER)
        self._model = user_input.get(CONF_MODEL)
        self._name = user_input.get(CONF_NAME)
        self._title = self._model or self._name

        await self.async_set_unique_id(self._ip)
        self.context["title_placeholders"] = {"model": self._title}

        return await self.async_step_confirm()
