"""Config flow to configure WiLight."""
import logging
from urllib.parse import urlparse

import pywilight

from homeassistant.components import ssdp
from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, ConfigFlow
from homeassistant.const import CONF_HOST

from . import PLATFORMS
from .const import DOMAIN  # pylint: disable=unused-import

CONF_SERIAL_NUMBER = "serial_number"
CONF_MODEL_NAME = "model_name"

WILIGHT_MANUFACTURER = "All Automacao Ltda"

_LOGGER = logging.getLogger(__name__)


class WiLightFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a WiLight config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
    def __init__(self):
        """Initialize the WiLight flow."""
        self._host = None
        self._serial_number = None
        self._device_id = None
        self._model_name = None
        self._components = []
        self._components_text = ""

    def _self_update(self, host, serial_number, model_name):
        self._host = host
        self._serial_number = serial_number
        self._device_id = f"WL{serial_number}"
        self._model_name = model_name
        self._components = pywilight.get_components_from_model(model_name)
        text = ""
        for component in self._components:
            if text == "":
                text = component
            else:
                text = ", ".join((text, component))
        self._components_text = text
        return text != ""

    def _get_entry(self):
        data = {
            CONF_HOST: self._host,
            CONF_SERIAL_NUMBER: self._serial_number,
            CONF_MODEL_NAME: self._model_name,
        }
        return self.async_create_entry(title=self._device_id, data=data)

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered WiLight."""
        # Filter out basic information
        if (
            ssdp.ATTR_SSDP_LOCATION not in discovery_info
            or ssdp.ATTR_UPNP_MANUFACTURER not in discovery_info
            or ssdp.ATTR_UPNP_SERIAL not in discovery_info
            or ssdp.ATTR_UPNP_MODEL_NAME not in discovery_info
            or ssdp.ATTR_UPNP_MODEL_NUMBER not in discovery_info
        ):
            return self.async_abort(reason="not_wilight")
        # Filter out non-WiLight devices
        if discovery_info.get(ssdp.ATTR_UPNP_MANUFACTURER) != WILIGHT_MANUFACTURER:
            return self.async_abort(reason="not_wilight")

        host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        serial_number = discovery_info[ssdp.ATTR_UPNP_SERIAL]
        model_name = discovery_info[ssdp.ATTR_UPNP_MODEL_NAME]

        if not self._self_update(host, serial_number, model_name):
            return self.async_abort(reason="not_wilight")

        component_ok = False
        for self_component in self._components:
            for component in PLATFORMS:
                if self_component == component:
                    component_ok = True
                    break

        if not component_ok:
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context["title_placeholders"] = {"name": self._device_id}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered WiLight."""
        if user_input is not None:
            return self._get_entry()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._device_id,
                "components": self._components_text,
            },
            errors={},
        )
