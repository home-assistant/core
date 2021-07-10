"""Config flow for MusicCast."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from aiohttp import ClientConnectorError
from aiomusiccast import MusicCastConnectionException, MusicCastDevice
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MusicCastFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a MusicCast config flow."""

    VERSION = 1

    serial_number: str | None = None
    host: str

    async def async_step_user(
        self, user_input: ConfigType | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""
        # Request user input, unless we are preparing discovery flow
        if user_input is None:
            return self._show_setup_form()

        host = user_input[CONF_HOST]
        serial_number = None

        errors = {}
        # Check if device is a MusicCast device

        try:
            info = await MusicCastDevice.get_device_info(
                host, async_get_clientsession(self.hass)
            )
        except (MusicCastConnectionException, ClientConnectorError):
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            serial_number = info.get("system_id")
            if serial_number is None:
                errors["base"] = "no_musiccast_device"

        if not errors:
            await self.async_set_unique_id(serial_number, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=host,
                data={
                    CONF_HOST: host,
                    "serial": serial_number,
                },
            )

        return self._show_setup_form(errors)

    def _show_setup_form(
        self, errors: dict | None = None
    ) -> data_entry_flow.FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors or {},
        )

    async def async_step_ssdp(self, discovery_info) -> data_entry_flow.FlowResult:
        """Handle ssdp discoveries."""
        if not await MusicCastDevice.check_yamaha_ssdp(
            discovery_info[ssdp.ATTR_SSDP_LOCATION], async_get_clientsession(self.hass)
        ):
            return self.async_abort(reason="yxc_control_url_missing")

        self.serial_number = discovery_info[ssdp.ATTR_UPNP_SERIAL]
        self.host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        await self.async_set_unique_id(self.serial_number)
        self._abort_if_unique_id_configured({CONF_HOST: self.host})
        self.context.update(
            {
                "title_placeholders": {
                    "name": discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME, self.host)
                }
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> data_entry_flow.FlowResult:
        """Allow the user to confirm adding the device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.host,
                data={
                    CONF_HOST: self.host,
                    "serial": self.serial_number,
                },
            )

        return self.async_show_form(step_id="confirm")

    async def async_step_import(self, import_data: dict) -> data_entry_flow.FlowResult:
        """Import data from configuration.yaml into the config flow."""
        res = await self.async_step_user(import_data)
        if res["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            _LOGGER.info(
                "Successfully imported %s from configuration.yaml",
                import_data.get(CONF_HOST),
            )
        elif res["type"] == data_entry_flow.RESULT_TYPE_FORM:
            _LOGGER.error(
                "Could not import %s from configuration.yaml",
                import_data.get(CONF_HOST),
            )
        return res
