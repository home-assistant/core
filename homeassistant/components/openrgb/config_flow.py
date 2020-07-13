"""Config flow for OpenRGB."""
import asyncio
import logging
import socket

from openrgb import OpenRGBClient
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT

from .const import CONN_TIMEOUT, DEFAULT_CLIENT_ID, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

RESULT_CONN_ERROR = "cannot_connect"
RESULT_LOG_MESSAGE = {RESULT_CONN_ERROR: "Connection error"}


@config_entries.HANDLERS.register(DOMAIN)
class OpenRGBFlowHandler(config_entries.ConfigFlow):
    """Config flow for OpenRGB component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Init OpenRGBFlowHandler."""
        self._errors = {}
        self._host = None
        self._port = DEFAULT_PORT
        self._client_id = DEFAULT_CLIENT_ID
        self._is_import = False

    def _try_connect(self):
        """Check if we can connect."""
        try:
            conn = OpenRGBClient(self._host, self._port, name=self._client_id)
            conn.comms.stop_connection()
        except (ConnectionError, socket.gaierror) as exc:
            raise CannotConnect from exc

        return True

    def _get_entry(self):
        return self.async_create_entry(
            title=DOMAIN,
            data={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_CLIENT_ID: self._client_id,
            },
        )

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        self._is_import = True
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._errors = {}

        data_schema = {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=self._port): int,
            vol.Optional(CONF_CLIENT_ID, default=self._client_id): str,
        }

        if user_input is not None:
            self._host = str(user_input[CONF_HOST])
            self._port = user_input[CONF_PORT]
            self._client_id = user_input[CONF_CLIENT_ID]

            try:
                await asyncio.wait_for(
                    self.hass.async_add_executor_job(self._try_connect),
                    timeout=CONN_TIMEOUT,
                )

                return self._get_entry()
            except (asyncio.TimeoutError, CannotConnect):
                result = RESULT_CONN_ERROR

            if self._is_import:
                _LOGGER.error(
                    "Error importing from configuration.yaml: %s",
                    RESULT_LOG_MESSAGE.get(result, "Generic Error"),
                )
                return self.async_abort(reason=result)

            self._errors["base"] = result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we can not connect."""
