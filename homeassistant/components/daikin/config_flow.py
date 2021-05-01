"""Config flow for the Daikin platform."""
import asyncio
import logging
from uuid import uuid4

from aiohttp import ClientError, web_exceptions
from async_timeout import timeout
from pydaikin.daikin_base import Appliance
from pydaikin.discovery import Discovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD

from .const import CONF_UUID, DOMAIN, KEY_MAC, TIMEOUT

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Daikin config flow."""
        self.host = None

    @property
    def schema(self):
        """Return current schema."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=self.host): str,
                vol.Optional(CONF_API_KEY): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )

    async def _create_entry(self, host, mac, key=None, uuid=None, password=None):
        """Register new entry."""
        if not self.unique_id:
            await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=host,
            data={
                CONF_HOST: host,
                KEY_MAC: mac,
                CONF_API_KEY: key,
                CONF_UUID: uuid,
                CONF_PASSWORD: password,
            },
        )

    async def _create_device(self, host, key=None, password=None):
        """Create device."""
        # BRP07Cxx devices needs uuid together with key
        if key:
            uuid = str(uuid4())
        else:
            uuid = None
            key = None

        if not password:
            password = None

        try:
            with timeout(TIMEOUT):
                device = await Appliance.factory(
                    host,
                    self.hass.helpers.aiohttp_client.async_get_clientsession(),
                    key=key,
                    uuid=uuid,
                    password=password,
                )
        except asyncio.TimeoutError:
            return self.async_show_form(
                step_id="user",
                data_schema=self.schema,
                errors={"base": "cannot_connect"},
            )
        except web_exceptions.HTTPForbidden:
            return self.async_show_form(
                step_id="user",
                data_schema=self.schema,
                errors={"base": "invalid_auth"},
            )
        except ClientError:
            _LOGGER.exception("ClientError")
            return self.async_show_form(
                step_id="user",
                data_schema=self.schema,
                errors={"base": "unknown"},
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device")
            return self.async_show_form(
                step_id="user",
                data_schema=self.schema,
                errors={"base": "unknown"},
            )

        mac = device.mac
        return await self._create_entry(host, mac, key, uuid, password)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.schema)
        return await self._create_device(
            user_input[CONF_HOST],
            user_input.get(CONF_API_KEY),
            user_input.get(CONF_PASSWORD),
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        host = user_input.get(CONF_HOST)
        if not host:
            return await self.async_step_user()
        return await self._create_device(host)

    async def async_step_zeroconf(self, discovery_info):
        """Prepare configuration for a discovered Daikin device."""
        _LOGGER.debug("Zeroconf user_input: %s", discovery_info)
        devices = Discovery().poll(ip=discovery_info[CONF_HOST])
        if not devices:
            _LOGGER.debug(
                "Could not find MAC-address for %s,"
                " make sure the required UDP ports are open (see integration documentation)",
                discovery_info[CONF_HOST],
            )
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(next(iter(devices))[KEY_MAC])
        self._abort_if_unique_id_configured()
        self.host = discovery_info[CONF_HOST]
        return await self.async_step_user()
