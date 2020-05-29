"""Config flow to configure the Arcam FMJ component."""
import asyncio
import logging
from urllib.parse import urlparse

import aiohttp
from defusedxml import ElementTree
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_UDN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, DOMAIN_DATA_ENTRIES

_LOGGER = logging.getLogger(__name__)


def _strip_uuid_prefix(data):
    return data[5:].split("-")[4]


def _log_exception(msg, *args):
    """Log an error and turn on traceback if debug is on."""
    _LOGGER.error(msg, *args, exc_info=_LOGGER.getEffectiveLevel() == logging.DEBUG)


async def _get_uniqueid_from_device_description(hass, url):
    """Retrieve and extract unique id from url."""
    try:
        session = async_get_clientsession(hass)
        async with session.get(url) as req:
            req.raise_for_status()
            data = await req.text()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        _log_exception("Unable to get device description from %s", url)
        return None

    try:
        xml = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        _log_exception("Unable to parse xml from %s", url)
        return None

    udn = xml.findtext("d:device/d:UDN", None, {"d": "urn:schemas-upnp-org:device-1-0"})
    return _strip_uuid_prefix(udn)


async def _get_uniqueid_from_host(hass, host):
    """Try to deduce a unique id from a host based on ssdp/upnp."""
    return await _get_uniqueid_from_device_description(
        hass, f"http://{host}:8080/dd.xml"
    )


def get_entry_client(hass, entry):
    """Retrieve client associated with a config entry."""
    return hass.data[DOMAIN_DATA_ENTRIES][entry.entry_id]


@config_entries.HANDLERS.register(DOMAIN)
class ArcamFmjFlowHandler(config_entries.ConfigFlow):
    """Handle a SimpliSafe config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _async_set_unique_id_and_update(self, host, port, uuid):
        config = {
            CONF_HOST: host,
            CONF_PORT: port,
        }
        entry = await self.async_set_unique_id(uuid)
        await self._abort_if_unique_id_configured(config)

    async def _async_create_entry(self, host, port):
        return self.async_create_entry(
            title=f"{DEFAULT_NAME} ({host})", data={CONF_HOST: host, CONF_PORT: port},
        )

    async def async_step_user(self, user_info):
        """Handle a discovered device."""
        errors = {}

        if user_info is not None:
            uuid = await _get_uniqueid_from_host(self.hass, user_info[CONF_HOST])
            if uuid:
                await self._async_set_unique_id_and_update(
                    user_info[CONF_HOST], user_info[CONF_PORT], uuid
                )

            return await self._async_create_entry(
                user_info[CONF_HOST], user_info[CONF_PORT]
            )

        fields = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        context = self.context  # pylint: disable=no-member
        placeholders = {
            "host": context[CONF_HOST],
        }
        context["title_placeholders"] = placeholders

        if user_input is not None:
            return await self._async_create_entry(
                context[CONF_HOST], context[CONF_PORT]
            )

        return self.async_show_form(
            step_id="confirm", description_placeholders=placeholders
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered device."""
        host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        port = DEFAULT_PORT
        uuid = _strip_uuid_prefix(discovery_info[ATTR_UPNP_UDN])

        await self._async_set_unique_id_and_update(host, port, uuid)

        context = self.context  # pylint: disable=no-member
        context[CONF_HOST] = host
        context[CONF_PORT] = DEFAULT_PORT
        return await self.async_step_confirm(None)
