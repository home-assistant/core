"""Config flow for devolo Home Network integration."""
from __future__ import annotations

import logging
from typing import Any

from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceNotFound
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PRODUCT, SERIAL_NUMBER, TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    zeroconf_instance = await zeroconf.async_get_instance(hass)
    async_client = get_async_client(hass)

    device = Device(data[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance)

    await device.async_connect(session_instance=async_client)
    await device.async_disconnect()

    return {
        SERIAL_NUMBER: str(device.serial_number),
        TITLE: device.hostname.split(".")[0],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for devolo Home Network."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            info = await validate_input(self.hass, user_input)
        except DeviceNotFound:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info[SERIAL_NUMBER], raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info[TITLE], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        if discovery_info.properties["MT"] in ["2600", "2601"]:
            return self.async_abort(reason="home_control")

        await self.async_set_unique_id(discovery_info.properties["SN"])
        self._abort_if_unique_id_configured()

        self.context[CONF_HOST] = discovery_info.host
        self.context["title_placeholders"] = {
            PRODUCT: discovery_info.properties["Product"],
            CONF_NAME: discovery_info.hostname.split(".")[0],
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by zeroconf."""
        title = self.context["title_placeholders"][CONF_NAME]
        if user_input is not None:
            data = {
                CONF_IP_ADDRESS: self.context[CONF_HOST],
            }
            return self.async_create_entry(title=title, data=data)
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"host_name": title},
        )
