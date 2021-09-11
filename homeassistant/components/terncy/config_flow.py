"""Config flow for Terncy integration."""
import logging
import uuid

import terncy
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP,
    CONF_NAME,
    CONF_PORT,
    DOMAIN,
    TERNCY_HUB_SVC_NAME,
)
from .hub_monitor import TerncyHubManager

_LOGGER = logging.getLogger(__name__)


async def _start_discovery(mgr):
    await mgr.start_discovery()


def _get_discovered_devices(mgr):
    return {} if mgr is None else mgr.hubs


def _get_terncy_instance(flow):
    return flow.terncy


class TerncyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Terncy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_devices = {}

        self.username = "ha_user_" + uuid.uuid4().hex[0:5]
        self.client_id = "homeass_nbhQ43"
        self.identifier = ""
        self.name = ""
        self.host = ""
        self.port = 443
        self.token = ""
        self.token_id = 0
        self.context = {}
        self.terncy = terncy.Terncy(
            self.client_id,
            self.identifier,
            self.host,
            self.port,
            self.username,
            "VALID_TOKEN_NOT_ACQUIRED",
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        devices_name = {}
        mgr = TerncyHubManager.instance(self.hass)
        if user_input is not None and CONF_DEVICE in user_input:
            devid = user_input[CONF_DEVICE]
            hub = _get_discovered_devices(mgr)[devid]
            self.identifier = devid
            self.name = hub[CONF_NAME]
            self.host = hub[CONF_IP]
            self.port = hub[CONF_PORT]
            _LOGGER.info("construct Terncy obj for %s %s", self.name, self.host)
            self.terncy = terncy.Terncy(
                self.client_id, self.identifier, self.host, self.port, self.username, ""
            )
            return self.async_show_form(
                step_id="begin_pairing",
                description_placeholders={"name": self.name},
            )

        for devid, hub in _get_discovered_devices(mgr).items():
            devices_name[devid] = hub[CONF_NAME]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    async def async_step_begin_pairing(self, user_input=None):
        """Start pairing process for the next available protocol."""
        if self.unique_id is None:
            await self.async_set_unique_id(self.identifier)
            self._abort_if_unique_id_configured()
        ternobj = _get_terncy_instance(self)
        if self.token == "":
            _LOGGER.warning("request a new token form terncy %s", self.identifier)
            code, token_id, token, state = await ternobj.request_token(
                self.username, "HA User"
            )
            self.token = token
            self.token_id = token_id
            self.terncy.token = token
        ternobj = _get_terncy_instance(self)
        code, state = await ternobj.check_token_state(self.token_id, self.token)
        if code != 200:
            _LOGGER.warning("current token invalid, clear it")
            self.token = ""
            self.token_id = 0
            errors = {}
            errors["base"] = "need_new_auth"
            return self.async_show_form(
                step_id="begin_pairing",
                description_placeholders={"name": self.name},
                errors=errors,
            )
        if state == terncy.TokenState.APPROVED.value:
            _LOGGER.warning("token valid, create entry for %s", self.identifier)
            return self.async_create_entry(
                title=self.name,
                data={
                    "identifier": self.identifier,
                    "username": self.username,
                    "token": self.token,
                    "token_id": self.token_id,
                    "host": self.host,
                    "port": self.port,
                },
            )
        errors = {}
        errors["base"] = "invalid_auth"
        return self.async_show_form(
            step_id="begin_pairing",
            description_placeholders={"name": self.name},
            errors=errors,
        )

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            return await self.async_step_begin_pairing()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": self.name}
        )

    async def async_step_zeroconf(self, discovery_info):
        """Prepare configuration for a discovered Daikin device."""
        identifier = discovery_info["name"]
        identifier = identifier.replace("." + TERNCY_HUB_SVC_NAME, "")
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        properties = discovery_info["properties"]
        name = properties[CONF_NAME]
        self.context["identifier"] = self.unique_id
        self.context["title_placeholders"] = {"name": name}
        self.identifier = identifier
        self.name = name
        self.host = discovery_info[CONF_HOST]
        self.port = discovery_info[CONF_PORT]
        self.terncy.ip = self.host
        self.terncy.port = self.port
        mgr = TerncyHubManager.instance(self.hass)
        _LOGGER.info("start discovery engine of domain %s", DOMAIN)
        await _start_discovery(mgr)
        return await self.async_step_confirm()
