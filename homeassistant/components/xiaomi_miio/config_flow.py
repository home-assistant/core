"""Config flow to configure Xiaomi Miio."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.helpers.device_registry import format_mac

# pylint: disable=unused-import
from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
    MODELS_SWITCH,
)
from .device import ConnectXiaomiDevice
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

DEFAULT_GATEWAY_NAME = "Xiaomi Gateway"
DEFAULT_DEVICE_NAME = "Xiaomi Device"
ZEROCONF_GATEWAY = "lumi-gateway"
ZEROCONF_ACPARTNER = "lumi-acpartner"

DEVICE_SETTINGS = {
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
}
DEVICE_CONFIG = vol.Schema({vol.Required(CONF_HOST): str}).extend(DEVICE_SETTINGS)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_GATEWAY, default=False): bool,
        vol.Optional(CONF_DEVICE, default=False): bool,
    }
)


class XiaomiMiioFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Xiaomi Miio config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.host = None

    async def async_step_import(self, conf: dict):
        """Import a configuration from config.yaml."""
        return await self.async_step_device(user_input=conf)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Check which device needs to be connected.
            if user_input[CONF_GATEWAY]:
                return await self.async_step_gateway()
            if user_input[CONF_DEVICE]:
                return await self.async_step_device()

            errors["base"] = "no_device_selected"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""
        name = discovery_info.get("name")
        self.host = discovery_info.get("host")
        mac_address = discovery_info.get("properties", {}).get("mac")

        if not name or not self.host or not mac_address:
            return self.async_abort(reason="not_xiaomi_miio")

        # Check which device is discovered.
        if name.startswith(ZEROCONF_GATEWAY) or name.startswith(ZEROCONF_ACPARTNER):
            unique_id = format_mac(mac_address)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured({CONF_HOST: self.host})

            # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
            self.context.update(
                {"title_placeholders": {"name": f"Gateway {self.host}"}}
            )

            return await self.async_step_gateway()
        for switch_model in MODELS_SWITCH:
            if name.startswith(switch_model.replace(".", "-")):
                unique_id = format_mac(mac_address)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured({CONF_HOST: self.host})

                # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
                self.context.update(
                    {"title_placeholders": {"name": f"Miio Device {self.host}"}}
                )

                return await self.async_step_device()

        # Discovered device is not yet supported
        _LOGGER.debug(
            "Not yet supported Xiaomi Miio device '%s' discovered with host %s",
            name,
            self.host,
        )
        return self.async_abort(reason="not_xiaomi_miio")

    async def async_step_gateway(self, user_input=None):
        """Handle a flow initialized by the user to configure a gateway."""
        errors = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            if user_input.get(CONF_HOST):
                self.host = user_input[CONF_HOST]

            # Try to connect to a Xiaomi Gateway.
            connect_gateway_class = ConnectXiaomiGateway(self.hass)
            await connect_gateway_class.async_connect_gateway(self.host, token)
            gateway_info = connect_gateway_class.gateway_info

            if gateway_info is not None:
                mac = format_mac(gateway_info.mac_address)
                unique_id = mac
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_GATEWAY_NAME,
                    data={
                        CONF_FLOW_TYPE: CONF_GATEWAY,
                        CONF_HOST: self.host,
                        CONF_TOKEN: token,
                        CONF_MODEL: gateway_info.model,
                        CONF_MAC: mac,
                    },
                )

            errors["base"] = "cannot_connect"

        if self.host:
            schema = vol.Schema(DEVICE_SETTINGS)
        else:
            schema = DEVICE_CONFIG

        return self.async_show_form(
            step_id="gateway", data_schema=schema, errors=errors
        )

    async def async_step_device(self, user_input=None):
        """Handle a flow initialized by the user to configure a xiaomi miio device."""
        errors = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            if user_input.get(CONF_HOST):
                self.host = user_input[CONF_HOST]

            # Try to connect to a Xiaomi Device.
            connect_device_class = ConnectXiaomiDevice(self.hass)
            await connect_device_class.async_connect_device(self.host, token)
            device_info = connect_device_class.device_info

            if device_info is not None:
                name = user_input.get(CONF_NAME, DEFAULT_DEVICE_NAME)

                if device_info.model in MODELS_SWITCH:
                    mac = format_mac(device_info.mac_address)
                    unique_id = mac
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_FLOW_TYPE: CONF_DEVICE,
                            CONF_HOST: self.host,
                            CONF_TOKEN: token,
                            CONF_MODEL: device_info.model,
                            CONF_MAC: mac,
                        },
                    )
                errors["base"] = "unknown_device"
            else:
                errors["base"] = "cannot_connect"

        if self.host:
            schema = vol.Schema(DEVICE_SETTINGS)
        else:
            schema = DEVICE_CONFIG

        return self.async_show_form(step_id="device", data_schema=schema, errors=errors)
