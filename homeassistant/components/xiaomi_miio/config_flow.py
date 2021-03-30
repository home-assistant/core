"""Config flow to configure Xiaomi Miio."""
import logging
from re import search

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
    MODELS_ALL,
    MODELS_ALL_DEVICES,
    MODELS_GATEWAY,
)
from .device import ConnectXiaomiDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_GATEWAY_NAME = "Xiaomi Gateway"

DEVICE_SETTINGS = {
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
}
DEVICE_CONFIG = vol.Schema({vol.Required(CONF_HOST): str}).extend(DEVICE_SETTINGS)
DEVICE_MODEL_CONFIG = {vol.Optional(CONF_MODEL): vol.In(MODELS_ALL)}


class XiaomiMiioFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Miio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.host = None
        self.mac = None

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        host = conf[CONF_HOST]
        self.context.update({"title_placeholders": {"name": f"YAML import {host}"}})
        return await self.async_step_device(user_input=conf)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_device()

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""
        name = discovery_info.get("name")
        self.host = discovery_info.get("host")
        self.mac = discovery_info.get("properties", {}).get("mac")
        if self.mac is None:
            poch = discovery_info.get("properties", {}).get("poch", "")
            result = search(r"mac=\w+", poch)
            if result is not None:
                self.mac = result.group(0).split("=")[1]

        if not name or not self.host or not self.mac:
            return self.async_abort(reason="not_xiaomi_miio")

        self.mac = format_mac(self.mac)

        # Check which device is discovered.
        for gateway_model in MODELS_GATEWAY:
            if name.startswith(gateway_model.replace(".", "-")):
                unique_id = self.mac
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                self.context.update(
                    {"title_placeholders": {"name": f"Gateway {self.host}"}}
                )

                return await self.async_step_device()

        for device_model in MODELS_ALL_DEVICES:
            if name.startswith(device_model.replace(".", "-")):
                unique_id = self.mac
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                self.context.update(
                    {"title_placeholders": {"name": f"{device_model} {self.host}"}}
                )

                return await self.async_step_device()

        # Discovered device is not yet supported
        _LOGGER.debug(
            "Not yet supported Xiaomi Miio device '%s' discovered with host %s",
            name,
            self.host,
        )
        return self.async_abort(reason="not_xiaomi_miio")

    async def async_step_device(self, user_input=None):
        """Handle a flow initialized by the user to configure a xiaomi miio device."""
        errors = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            model = user_input.get(CONF_MODEL)
            if user_input.get(CONF_HOST):
                self.host = user_input[CONF_HOST]

            # Try to connect to a Xiaomi Device.
            connect_device_class = ConnectXiaomiDevice(self.hass)
            await connect_device_class.async_connect_device(self.host, token)
            device_info = connect_device_class.device_info

            if model is None and device_info is not None:
                model = device_info.model

            if model is not None:
                if self.mac is None and device_info is not None:
                    self.mac = format_mac(device_info.mac_address)

                # Setup Gateways
                for gateway_model in MODELS_GATEWAY:
                    if model.startswith(gateway_model):
                        unique_id = self.mac
                        await self.async_set_unique_id(
                            unique_id, raise_on_progress=False
                        )
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=DEFAULT_GATEWAY_NAME,
                            data={
                                CONF_FLOW_TYPE: CONF_GATEWAY,
                                CONF_HOST: self.host,
                                CONF_TOKEN: token,
                                CONF_MODEL: model,
                                CONF_MAC: self.mac,
                            },
                        )

                # Setup all other Miio Devices
                name = user_input.get(CONF_NAME, model)

                for device_model in MODELS_ALL_DEVICES:
                    if model.startswith(device_model):
                        unique_id = self.mac
                        await self.async_set_unique_id(
                            unique_id, raise_on_progress=False
                        )
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=name,
                            data={
                                CONF_FLOW_TYPE: CONF_DEVICE,
                                CONF_HOST: self.host,
                                CONF_TOKEN: token,
                                CONF_MODEL: model,
                                CONF_MAC: self.mac,
                            },
                        )
                errors["base"] = "unknown_device"
            else:
                errors["base"] = "cannot_connect"

        if self.host:
            schema = vol.Schema(DEVICE_SETTINGS)
        else:
            schema = DEVICE_CONFIG

        if errors:
            schema = schema.extend(DEVICE_MODEL_CONFIG)

        return self.async_show_form(step_id="device", data_schema=schema, errors=errors)
