"""Config flow for Samsung TV."""
from socket import gethostbyname
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
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
)

from .bridge import SamsungTVBridge
from .const import (
    ATTR_PROPERTIES,
    CONF_MANUFACTURER,
    CONF_MODEL,
    DOMAIN,
    LOGGER,
    METHOD_LEGACY,
    METHOD_WEBSOCKET,
    MODEL_SOUNDBAR,
    RESULT_AUTH_MISSING,
    RESULT_NOT_SUCCESSFUL,
    RESULT_NOT_SUPPORTED,
    RESULT_SUCCESS,
    WEBSOCKET_PORTS,
)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_NAME): str})
SUPPORTED_METHODS = [METHOD_LEGACY, METHOD_WEBSOCKET]


class SamsungTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Samsung TV config flow."""

    VERSION = 1
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

    async def _abort_if_already_configured(self):
        device_ip = await self.hass.async_add_executor_job(gethostbyname, self._host)
        for entry in self._async_current_entries():

            # update user configured or unique_id=ip entries
            if self._id and not entry.unique_id or device_ip == entry.unique_id:
                data = {
                    key: value
                    for key, value in entry.data.items()
                    # clean up old entries
                    if key not in (CONF_ID, CONF_IP_ADDRESS)
                }
                if self._manufacturer and not data.get(CONF_MANUFACTURER):
                    data[CONF_MANUFACTURER] = self._manufacturer
                if self._model and not data.get(CONF_MODEL):
                    data[CONF_MODEL] = self._model
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=self._id, data=data
                )
                raise data_entry_flow.AbortFlow("already_configured")

            if (
                (self._host and self._host == entry.data.get(CONF_HOST))
                or (self._id and self._id == entry.unique_id)
                or (self._mac and self._mac == entry.data.get(CONF_MAC))
            ):
                raise data_entry_flow.AbortFlow("already_configured")

    def _try_connect(self):
        """Try to connect and check auth."""
        for method in SUPPORTED_METHODS:
            self._bridge = SamsungTVBridge.get_bridge(method, self._host)
            result = self._bridge.try_connect()
            if result == RESULT_SUCCESS:
                return
            if result != RESULT_NOT_SUCCESSFUL:
                raise data_entry_flow.AbortFlow(result)
        LOGGER.debug("No working config found")
        raise data_entry_flow.AbortFlow(RESULT_NOT_SUCCESSFUL)

    async def _get_and_check_device_info(self):
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

        if self._device_info:
            device_type = self._device_info.get("device", {}).get("type")
            if device_type and device_type != "Samsung SmartTV":
                raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)
            self._model = self._device_info.get("device", {}).get("modelName")
            return

        if self._bridge and self._bridge.method == METHOD_WEBSOCKET:
            raise data_entry_flow.AbortFlow(RESULT_NOT_SUPPORTED)

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input[CONF_NAME]
            self._title = self._name

            await self.hass.async_add_executor_job(self._try_connect)
            await self._get_and_check_device_info()

            await self.async_set_unique_id(self._id)
            await self._abort_if_unique_id_configured()

            return self._get_entry()

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_ssdp(self, user_input=None):
        """Handle a flow initialized by ssdp discovery."""
        self._host = urlparse(user_input[ATTR_SSDP_LOCATION]).hostname
        self._id = user_input.get(ATTR_UPNP_UDN)

        # probably access denied
        if self._id is None:
            return self.async_abort(reason=RESULT_AUTH_MISSING)
        if self._id.startswith("uuid:"):
            self._id = self._id[5:]

        await self.async_set_unique_id(self._id)
        await self._abort_if_already_configured()

        await self._get_and_check_device_info()

        self._manufacturer = user_input.get(ATTR_UPNP_MANUFACTURER)
        if not self._model:
            self._model = user_input.get(ATTR_UPNP_MODEL_NAME)

        if self._model.startswith(MODEL_SOUNDBAR):
            return self.async_abort(reason=RESULT_NOT_SUPPORTED)

        self._name = f"{self._manufacturer} {self._model}"
        self._title = self._model

        self.context["title_placeholders"] = {"model": self._model}
        return await self.async_step_confirm()

    async def async_step_zeroconf(self, user_input=None):
        """Handle a flow initialized by zeroconf discovery."""
        self._host = user_input[CONF_HOST]
        self._id = user_input[ATTR_PROPERTIES].get("serialNumber")

        if self._id:
            await self.async_set_unique_id(self._id)
            await self._abort_if_already_configured()

        await self._get_and_check_device_info()

        self._mac = user_input[ATTR_PROPERTIES].get("deviceid")
        self._manufacturer = user_input[ATTR_PROPERTIES].get("manufacturer")
        if not self._model:
            self._model = user_input[ATTR_PROPERTIES].get("model")
        self._name = f"{self._manufacturer} {self._model}"
        self._title = self._model

        self.context["title_placeholders"] = {"model": self._model}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""
        if user_input is not None:
            await self.hass.async_add_executor_job(self._try_connect)

            return self._get_entry()

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
