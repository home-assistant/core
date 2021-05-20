"""Config flow for Samsung TV."""
import socket
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.helpers.typing import DiscoveryInfoType

from .bridge import SamsungTVBridge
from .const import (
    ATTR_PROPERTIES,
    CONF_MANUFACTURER,
    CONF_MODEL,
    DOMAIN,
    LOGGER,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    RESULT_CANNOT_CONNECT,
    RESULT_ID_MISSING,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    RESULT_UNKNOWN_HOST,
    WEBSOCKET_PORTS,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})
SUPPORTED_METHODS = [METHOD_LEGACY, METHOD_WEBSOCKET]


def _get_device_info(host):
    """Fetch device info by any websocket method."""
    for port in WEBSOCKET_PORTS:
        if device_info := SamsungTVBridge.get_bridge(
            METHOD_WEBSOCKET, host, port
        ).device_info():
            return device_info
    return None


async def async_get_device_info(hass, bridge, host):
    """Fetch device info from bridge or websocket."""
    if bridge:
        return await hass.async_add_executor_job(bridge.device_info)

    return await hass.async_add_executor_job(_get_device_info, host)


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 2

    def __init__(self):
        """Initialize flow."""
        self._host = None
        self._mac = None
        self._manufacturer = None
        self._model = None
        self._name = None
        self._title = None
        self._id = None
        self._bridge = None
        self._device_info = None

    def _get_entry(self):
        """Get device entry."""
        data = {
            CONF_HOST: self._host,
            CONF_MAC: self._mac,
            CONF_MANUFACTURER: self._manufacturer,
            CONF_METHOD: self._bridge.method,
            CONF_MODEL: self._model,
            CONF_NAME: self._name,
            CONF_PORT: self._bridge.port,
        }
        if self._bridge.token:
            data[CONF_TOKEN] = self._bridge.token
        return self.async_create_entry(
            title=self._title,
            data=data,
        )

    async def _async_set_device_unique_id(self, raise_on_progress=True):
        """Set device unique_id."""
        await self._async_get_and_check_device_info()
        udn = self._device_info.get("device", {}).get(ATTR_UPNP_UDN.lower())
        await self._async_set_unique_id_from_udn(udn, raise_on_progress)

    async def _async_set_unique_id_from_udn(self, udn, raise_on_progress=True):
        """Set the unique id from the udn."""
        if not udn:
            LOGGER.debug(
                "Property " "%s" " is missing for host %s",
                ATTR_UPNP_UDN.lower(),
                self._host,
            )
            return self.async_abort(reason=RESULT_ID_MISSING)

        if udn.startswith("uuid:"):
            unique_id = udn[5:]
        else:
            unique_id = udn

        await self.async_set_unique_id(unique_id, raise_on_progress=raise_on_progress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

    def _try_connect(self):
        """Try to connect and check auth."""
        if self._bridge:
            return

        for method in SUPPORTED_METHODS:
            self._bridge = SamsungTVBridge.get_bridge(method, self._host)
            result = self._bridge.try_connect()
            if result == RESULT_SUCCESS:
                return
            if result != RESULT_CANNOT_CONNECT:
                raise data_entry_flow.AbortFlow(result)
        LOGGER.debug("No working config found")
        raise data_entry_flow.AbortFlow(RESULT_CANNOT_CONNECT)

    async def _async_get_and_check_device_info(self):
        """Try to get the device info."""
        device_info = await async_get_device_info(self.hass, self._bridge, self._host)
        if not device_info:
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
        dev_info = device_info.get("device", {})
        device_type = dev_info.get("type")
        if device_type and device_type != "Samsung SmartTV":
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
        self._model = dev_info.get("modelName")
        self._manufacturer = "Samsung"
        if "name" in dev_info:
            self._name = dev_info.get("name").replace("[TV] ", "")
        else:
            self._name = device_type
        self._title = f"{self._name} ({self._model})"
        if dev_info.get("networkType") == "wireless":
            self._mac = dev_info.get("wifiMac")
        self._device_info = device_info

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            try:
                self._host = await self.hass.async_add_executor_job(
                    socket.gethostbyname, user_input[CONF_HOST]
                )
            except socket.gaierror as err:
                raise data_entry_flow.AbortFlow(RESULT_UNKNOWN_HOST) from err
            self._name = user_input[CONF_NAME]
            self._title = self._name

            await self.hass.async_add_executor_job(self._try_connect)

            if self._bridge.method == METHOD_LEGACY:
                # Legacy bridge does not provide device info
                self._async_abort_entries_match({CONF_HOST: self._host})
            else:
                await self._async_set_device_unique_id(raise_on_progress=False)

            return self._get_entry()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    @callback
    def _async_start_discovery_for_host(self, host):
        """Start discovery for a host."""
        self._host = host
        self._async_abort_entries_match({CONF_HOST: host})
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == self.discovered_ip:
                raise data_entry_flow.AbortFlow("already_in_progress")

    async def async_step_ssdp(self, discovery_info: DiscoveryInfoType):
        """Handle a flow initialized by ssdp discovery."""
        self._async_start_discovery_for_host(
            urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        )
        await self._async_set_unique_id_from_udn(discovery_info.get(ATTR_UPNP_UDN))

        self._manufacturer = discovery_info.get(ATTR_UPNP_MANUFACTURER)
        self._model = discovery_info.get(ATTR_UPNP_MODEL_NAME)
        self._title = self._model

        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_dhcp(self, discovery_info: DiscoveryInfoType):
        """Handle a flow initialized by dhcp discovery."""

        self._async_start_discovery_for_host(discovery_info[IP_ADDRESS])
        await self._async_set_device_unique_id()

        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle a flow initialized by zeroconf discovery."""

        self._async_start_discovery_for_host(discovery_info[CONF_HOST])
        await self._async_set_device_unique_id()

        self._mac = discovery_info[ATTR_PROPERTIES].get("deviceid")
        self._manufacturer = discovery_info[ATTR_PROPERTIES].get("manufacturer")
        if not self._model:
            self._model = discovery_info[ATTR_PROPERTIES].get("model")

        self.context["title_placeholders"] = {"device": self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:

            await self.hass.async_add_executor_job(self._try_connect)
            return self._get_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"device": self._title}
        )

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        self._host = user_input[CONF_HOST]
        self._manufacturer = user_input.get(CONF_MANUFACTURER)
        self._model = user_input.get(CONF_MODEL)
        self._name = user_input.get(CONF_NAME)
        self._title = f"{self._name} ({self._model})"

        await self.async_set_unique_id(self._id)
        self.context["title_placeholders"] = {"device": self._title}

        return await self.async_step_confirm()
