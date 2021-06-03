"""Config flow for MusicCast."""
# import my_pypi_dependency

import logging
from typing import Dict, Optional
from urllib.parse import urlparse

from aiohttp import ClientConnectorError
from aiomusiccast import MusicCastDevice
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from ... import data_entry_flow
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MusicCastFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MusicCast config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize a new Flow."""
        self.serial_number = None
        self.model_name = None
        self.host = None

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""
        return await self._handle_config_flow(user_input)

    async def _handle_config_flow(
        self, user_input: Optional[ConfigType] = None
    ) -> data_entry_flow.FlowResult:
        """Config flow handler for MusicCast."""

        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self._show_setup_form()

        title = user_input[CONF_HOST]
        self.host = user_input[CONF_HOST]

        errors = {}
        # Check if device is a MusicCast device

        try:
            info = await MusicCastDevice.get_device_info(
                user_input[CONF_HOST], async_get_clientsession(self.hass)
            )
            if self.serial_number is None:
                self.serial_number = info["serial_number"]
            if self.model_name is None:
                self.model_name = info["model_name"]
            unique_id = f"{self.model_name}-{self.serial_number}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
        except ClientConnectorError:
            errors["base"] = "cannot_connect"
        except KeyError:
            errors["base"] = "no_musiccast_device"
        except Exception as e:
            _LOGGER.error(e)
            errors["base"] = "unknown"

        if not errors:
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    "model": self.model_name,
                    "serial": self.serial_number,
                },
            )

        return self._show_setup_form(errors)

    def _show_setup_form(
        self, errors: Optional[Dict] = None
    ) -> data_entry_flow.FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle ssdp discoveries."""
        if not await MusicCastDevice.check_yamaha_ssdp(
            discovery_info[ssdp.ATTR_SSDP_LOCATION], async_get_clientsession(self.hass)
        ):
            return self.async_abort(reason="yxcControlURL_missing")

        self.model_name = discovery_info[ssdp.ATTR_UPNP_MODEL_NAME]
        self.serial_number = discovery_info[ssdp.ATTR_UPNP_SERIAL]
        self.host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        unique_id = f"{self.model_name}-{self.serial_number}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured({CONF_HOST: self.host})
        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME, self.host)
                }
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.host,
                data={
                    CONF_HOST: self.host,
                    "model": self.model_name,
                    "serial": self.serial_number,
                },
            )

        return self.async_show_form(step_id="confirm")
