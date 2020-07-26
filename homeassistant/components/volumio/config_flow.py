"""Config flow for Volumio integration."""
import logging
from typing import Optional

from pyvolumio import CannotConnectError, Volumio
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema({"host": str, "port": int})


async def validate_input(hass, host, port):
    """Validate the user input allows us to connect."""
    volumio = Volumio(host, port, async_get_clientsession(hass))

    try:
        return await volumio.get_system_info()
    except CannotConnectError as error:
        raise CannotConnect from error


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Volumio."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._host: Optional[str] = None
        self._port: Optional[int] = None
        self._name: Optional[str] = None
        self._uuid: Optional[str] = None

    @callback
    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                CONF_NAME: self._name,
                CONF_HOST: self._host,
                CONF_PORT: self._port,
                CONF_ID: self._uuid,
            },
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                self._host = user_input[CONF_HOST]
                self._port = user_input[CONF_PORT]
                info = await validate_input(self.hass, self._host, self._port)
                self._name = info.get("name", self._host)
                self._uuid = info.get("id", self._host)
                return self._async_get_entry()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        host = discovery_info["host"]
        port = int(discovery_info["port"])
        name = discovery_info["properties"]["volumioName"]
        uuid = discovery_info["properties"]["UUID"]

        # Check if already configured
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name}
        )

        self._host = discovery_info[CONF_HOST]
        self._port = discovery_info[CONF_PORT]
        self._name = name
        self._uuid = uuid

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            try:
                await validate_input(self.hass, self._host, self._port)
                return self._async_get_entry()
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders={"name": self._name}
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
