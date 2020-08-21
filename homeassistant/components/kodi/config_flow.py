"""Config flow for Kodi integration."""
import logging

from pykodi import CannotConnectError, InvalidAuthError, Kodi, get_kodi_connection
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType, Optional

from .const import (
    CONF_WS_PORT,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_WS_PORT,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_http(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect over HTTP."""

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    ssl = data.get(CONF_SSL)
    session = async_get_clientsession(hass)

    _LOGGER.debug("Connecting to %s:%s over HTTP.", host, port)
    khc = get_kodi_connection(
        host, port, None, username, password, ssl, session=session
    )
    kodi = Kodi(khc)
    try:
        await kodi.ping()
    except CannotConnectError as error:
        raise CannotConnect from error
    except InvalidAuthError as error:
        raise InvalidAuth from error


async def validate_ws(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect over WS."""
    ws_port = data.get(CONF_WS_PORT)
    if not ws_port:
        return

    host = data[CONF_HOST]
    port = data[CONF_PORT]
    username = data.get(CONF_USERNAME)
    password = data.get(CONF_PASSWORD)
    ssl = data.get(CONF_SSL)

    session = async_get_clientsession(hass)

    _LOGGER.debug("Connecting to %s:%s over WebSocket.", host, ws_port)
    kwc = get_kodi_connection(
        host, port, ws_port, username, password, ssl, session=session
    )
    try:
        await kwc.connect()
        if not kwc.connected:
            _LOGGER.warning("Cannot connect to %s:%s over WebSocket.", host, ws_port)
            raise CannotConnect()
        kodi = Kodi(kwc)
        await kodi.ping()
    except CannotConnectError as error:
        raise CannotConnect from error


class KodiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kodi."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._ws_port: Optional[int] = None
        self._name: Optional[str] = None
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._ssl: Optional[bool] = DEFAULT_SSL
        self._discovery_name: Optional[str] = None

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        self._host = discovery_info["host"]
        self._port = int(discovery_info["port"])
        self._name = discovery_info["hostname"][: -len(".local.")]
        uuid = discovery_info["properties"]["uuid"]
        self._discovery_name = discovery_info["name"]

        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_NAME: self._name,
            }
        )

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context.update({"title_placeholders": {CONF_NAME: self._name}})
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_host(user_input)

    async def async_step_host(self, user_input=None, errors=None):
        """Handle host name and port input."""
        if not errors:
            errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = user_input[CONF_PORT]
            self._ssl = user_input[CONF_SSL]
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="host", data_schema=self._host_schema(), errors=errors
        )

    async def async_step_credentials(self, user_input=None):
        """Handle username and password input."""
        errors = {}
        if user_input is not None:
            self._username = user_input.get(CONF_USERNAME)
            self._password = user_input.get(CONF_PASSWORD)
            try:
                await validate_http(self.hass, self._get_data())
                return await self.async_step_ws_port()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                if self._discovery_name:
                    return self.async_abort(reason="cannot_connect")
                return await self.async_step_host(errors={"base": "cannot_connect"})
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="credentials", data_schema=self._credentials_schema(), errors=errors
        )

    async def async_step_ws_port(self, user_input=None):
        """Handle websocket port of discovered node."""
        errors = {}
        if user_input is not None:
            self._ws_port = user_input.get(CONF_WS_PORT)
            try:
                await validate_ws(self.hass, self._get_data())
                return self._create_entry()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="ws_port", data_schema=self._ws_port_schema(), errors=errors
        )

    async def async_step_import(self, data):
        """Handle import from YAML."""
        # We assume that the imported values work and just create the entry
        return self.async_create_entry(title=data[CONF_NAME], data=data)

    @callback
    def _create_entry(self):
        return self.async_create_entry(
            title=self._name or self._host, data=self._get_data(),
        )

    @callback
    def _get_data(self):
        data = {
            CONF_NAME: self._name,
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_WS_PORT: self._ws_port,
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_SSL: self._ssl,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
        }

        return data

    @callback
    def _ws_port_schema(self):
        suggestion = self._ws_port or DEFAULT_WS_PORT
        return vol.Schema(
            {
                vol.Optional(
                    CONF_WS_PORT, description={"suggested_value": suggestion}
                ): int
            }
        )

    @callback
    def _host_schema(self):
        default_port = self._port or DEFAULT_PORT
        default_ssl = self._ssl or DEFAULT_SSL
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_PORT, default=default_port): int,
                vol.Required(CONF_SSL, default=default_ssl): bool,
            }
        )

    @callback
    def _credentials_schema(self):
        return vol.Schema(
            {
                vol.Optional(
                    CONF_USERNAME, description={"suggested_value": self._username}
                ): str,
                vol.Optional(
                    CONF_PASSWORD, description={"suggested_value": self._password}
                ): str,
            }
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
