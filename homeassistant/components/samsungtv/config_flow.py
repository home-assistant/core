"""Config flow for Samsung TV."""
import socket
from urllib.parse import urlparse

from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, UnhandledResponse
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
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
)

# pylint:disable=unused-import
from .const import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_ON_ACTION,
    DOMAIN,
    LOGGER,
    METHODS,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})

RESULT_AUTH_MISSING = "auth_missing"
RESULT_SUCCESS = "success"
RESULT_NOT_FOUND = "not_found"
RESULT_NOT_SUPPORTED = "not_supported"


def _get_ip(host):
    if host is None:
        return None
    return socket.gethostbyname(host)


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._ip = None
        self._manufacturer = None
        self._method = None
        self._model = None
        self._name = None
        self._on_script = None
        self._port = None
        self._title = None
        self._uuid = None

    def _get_entry(self):
        return self.async_create_entry(
            title=self._title,
            data={
                CONF_HOST: self._host,
                CONF_ID: self._uuid,
                CONF_IP_ADDRESS: self._ip,
                CONF_MANUFACTURER: self._manufacturer,
                CONF_METHOD: self._method,
                CONF_MODEL: self._model,
                CONF_NAME: self._name,
                CONF_ON_ACTION: self._on_script,
                CONF_PORT: self._port,
            },
        )

    def _try_connect(self):
        """Try to connect and check auth."""
        for method in METHODS:
            config = {
                "name": "HomeAssistant",
                "description": "HomeAssistant",
                "id": "ha.component.samsung",
                "host": self._host,
                "method": method,
                "port": self._port,
                "timeout": 1,
            }
            try:
                LOGGER.debug("Try config: %s", config)
                with Remote(config.copy()):
                    LOGGER.debug("Working config: %s", config)
                    self._method = method
                    return RESULT_SUCCESS
            except AccessDenied:
                LOGGER.debug("Working but denied config: %s", config)
                return RESULT_AUTH_MISSING
            except UnhandledResponse:
                LOGGER.debug("Working but unsupported config: %s", config)
                return RESULT_NOT_SUPPORTED
            except (OSError):
                LOGGER.debug("Failing config: %s", config)

        LOGGER.debug("No working config found")
        return RESULT_NOT_FOUND

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        self._on_script = user_input.get(CONF_ON_ACTION)
        self._port = user_input.get(CONF_PORT)

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
            self._title = user_input.get(CONF_NAME)

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result != RESULT_SUCCESS:
                return self.async_abort(reason=result)
            return self._get_entry()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_ssdp(self, user_input=None):
        """Handle a flow initialized by discovery."""
        host = urlparse(user_input[ATTR_SSDP_LOCATION]).hostname
        ip_address = await self.hass.async_add_executor_job(_get_ip, host)

        self._host = host
        self._ip = self.context[CONF_IP_ADDRESS] = ip_address
        self._manufacturer = user_input[ATTR_UPNP_MANUFACTURER]
        self._model = user_input[ATTR_UPNP_MODEL_NAME]
        self._name = user_input[ATTR_UPNP_FRIENDLY_NAME]
        if self._name.startswith("[TV]"):
            self._name = self._name[4:]
        self._title = f"{self._name} ({self._model})"
        self._uuid = user_input[ATTR_UPNP_UDN]
        if self._uuid.startswith("uuid:"):
            self._uuid = self._uuid[5:]

        config_entry = await self.async_set_unique_id(ip_address)
        if config_entry:
            config_entry.data[CONF_ID] = self._uuid
            config_entry.data[CONF_MANUFACTURER] = self._manufacturer
            config_entry.data[CONF_MODEL] = self._model
            self.hass.config_entries.async_update_entry(config_entry)
            return self.async_abort(reason="already_configured")

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
