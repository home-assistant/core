"""Config flow for Samsung TV."""
import socket
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
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


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

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

        if self._id:
            await self.async_set_unique_id(
                self._id, raise_on_progress=raise_on_progress
            )
            self._abort_if_unique_id_configured()

        await self._async_get_and_check_device_info()

        if uuid := self._device_info.get("device", {}).get(ATTR_UPNP_UDN.lower()):
            self._id = uuid

        if not self._id:
            LOGGER.debug(
                "Property " "%s" " is missing for host %s",
                ATTR_UPNP_UDN.lower(),
                self._host,
            )
            return self.async_abort(reason=RESULT_ID_MISSING)

        if self._id.startswith("uuid:"):
            self._id = self._id[5:]

        await self.async_set_unique_id(self._id, raise_on_progress=raise_on_progress)
        self._abort_if_unique_id_configured()

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
        if self._bridge:
            self._device_info = await self.hass.async_add_executor_job(
                self._bridge.device_info
            )
        else:
            for port in WEBSOCKET_PORTS:
                self._device_info = await self.hass.async_add_executor_job(
                    SamsungTVBridge.get_bridge(
                        METHOD_WEBSOCKET, self._host, port
                    ).device_info
                )
                if self._device_info:
                    break

            if not self._device_info:
                raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)

        device_type = self._device_info.get("device", {}).get("type")
        if device_type and device_type != "Samsung SmartTV":
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
        self._model = self._device_info.get("device", {}).get("modelName")

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

            await self._async_set_device_unique_id(raise_on_progress=False)

            return self._get_entry()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_ssdp(self, discovery_info: DiscoveryInfoType):
        """Handle a flow initialized by ssdp discovery."""
        self._host = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname

        LOGGER.debug("Found Samsung device via ssdp at %s", self._host)
        await self._async_set_device_unique_id()

        self._manufacturer = discovery_info.get(ATTR_UPNP_MANUFACTURER)
        if not self._model:
            self._model = discovery_info.get(ATTR_UPNP_MODEL_NAME)

        self._name = f"{self._manufacturer} {self._model}"
        self._title = self._model

        self.context["title_placeholders"] = {"model": self._model}
        return await self.async_step_confirm()

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle a flow initialized by zeroconf discovery."""
        self._host = discovery_info[CONF_HOST]

        LOGGER.debug("Found Samsung device via zeroconf at %s", self._host)

        await self._async_set_device_unique_id()

        self._mac = discovery_info[ATTR_PROPERTIES].get("deviceid")
        self._manufacturer = discovery_info[ATTR_PROPERTIES].get("manufacturer")
        if not self._model:
            self._model = discovery_info[ATTR_PROPERTIES].get("model")
        self._name = f"{self._manufacturer} {self._model}"
        self._title = self._model

        self.context["title_placeholders"] = {"model": self._model}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:

            await self.hass.async_add_executor_job(self._try_connect)
            return self._get_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"model": self._model}
        )

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        self._host = user_input[CONF_HOST]
        self._manufacturer = user_input.get(CONF_MANUFACTURER)
        self._model = user_input.get(CONF_MODEL)
        self._name = user_input.get(CONF_NAME)
        self._title = self._model or self._name

        await self.async_set_unique_id(self._id)
        self.context["title_placeholders"] = {"model": self._title}

        return await self.async_step_confirm()
