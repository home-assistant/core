"""Config flow for Samsung TV."""
from samsungctl import Remote
from samsungctl.exceptions import AccessDenied, UnhandledResponse
import socket
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

from .const import CONF_MANUFACTURER, CONF_MODEL, DOMAIN, LOGGER, METHODS


DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})

RESULT_AUTH_MISSING = "auth_missing"
RESULT_SUCCESS = "success"
RESULT_NOT_FOUND = "not_found"
RESULT_NOT_SUPPORTED = "not_supported"


def _get_ip(host):
    if host is None:
        return
    return socket.gethostbyname(host)


async def _async_try_connect(host, name):
    """Try to connect and check auth."""
    for method in METHODS:
        config = {
            "name": "HomeAssistant",
            "description": name,
            "id": "ha.component.samsung",
            "host": host,
            "method": method,
            "port": None,
            "timeout": None,
        }
        try:
            LOGGER.debug("Try config: %s", config)
            with Remote(config.copy()):
                LOGGER.debug("Working config: %s", config)
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

    def _is_already_configured(self):
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if self._ip == entry.data.get(CONF_IP_ADDRESS):
                return True
        return False

    async def _async_get_entry(self):
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

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                DATA_SCHEMA(user_input)
                self._host = user_input[CONF_HOST]
                self._title = user_input[CONF_NAME]
                self._ip = self.context[CONF_IP_ADDRESS] = _get_ip(self._host)

                if self._is_already_configured():
                    return self.async_abort(reason="already_configured")

                result = await _async_try_connect(self._host, self._title)

                if result == RESULT_NOT_FOUND:
                    return self.async_abort(reason=RESULT_NOT_FOUND)
                elif result == RESULT_NOT_SUPPORTED:
                    return self.async_abort(reason=RESULT_NOT_SUPPORTED)
                elif result == RESULT_AUTH_MISSING:
                    return self.async_abort(reason=RESULT_AUTH_MISSING)
                elif result == RESULT_SUCCESS:
                    return await self._async_get_entry()

            except vol.error.MultipleInvalid as errs:
                for err in errs.errors:
                    errors[err.path[0]] = err.msg

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, user_input=None):
        """Handle a flow initialized by discovery."""
        self._host = user_input[ATTR_HOST]
        self._ip = self.context[CONF_IP_ADDRESS] = _get_ip(user_input[ATTR_HOST])
        self._manufacturer = user_input[ATTR_MANUFACTURER]
        self._model = user_input[ATTR_MODEL_NAME]
        self._uuid = user_input[ATTR_UDN]
        if self._uuid.startswith("uuid:"):
            self._uuid = self._uuid[5:]
        self._name = user_input[ATTR_NAME]
        if self._name.startswith("[TV]"):
            self._name = self._name[4:]
        self._title = "{} ({})".format(self._name, self._model)

        if any(
            self._ip == flow["context"].get(CONF_IP_ADDRESS)
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        if self._is_already_configured():
            return self.async_abort(reason="already_configured")

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            result = await _async_try_connect(self._host, self._name)

            if result == RESULT_NOT_FOUND:
                return self.async_abort(reason=RESULT_NOT_FOUND)
            elif result == RESULT_NOT_SUPPORTED:
                return self.async_abort(reason=RESULT_NOT_SUPPORTED)
            elif result == RESULT_AUTH_MISSING:
                return self.async_abort(reason=RESULT_AUTH_MISSING)
            elif result == RESULT_SUCCESS:
                return await self._async_get_entry()

        return self.async_show_form(
            step_id="confirm", description_placeholders={"model": self._model}
        )
