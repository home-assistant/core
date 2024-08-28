"""Config flow to configure WiLight."""

from urllib.parse import urlparse

import pywilight

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from . import DOMAIN

CONF_SERIAL_NUMBER = "serial_number"
CONF_MODEL_NAME = "model_name"

WILIGHT_MANUFACTURER = "All Automacao Ltda"

# List the components supported by this integration.
ALLOWED_WILIGHT_COMPONENTS = ["cover", "fan", "light", "switch"]


class WiLightFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a WiLight config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the WiLight flow."""
        self._host = None
        self._serial_number = None
        self._title = None
        self._model_name = None
        self._wilight_components: list[str] = []
        self._components_text = ""

    def _wilight_update(self, host, serial_number, model_name):
        self._host = host
        self._serial_number = serial_number
        self._title = f"WL{serial_number}"
        self._model_name = model_name
        self._wilight_components = pywilight.get_components_from_model(model_name)
        self._components_text = ", ".join(self._wilight_components)
        return self._components_text != ""

    def _get_entry(self):
        data = {
            CONF_HOST: self._host,
            CONF_SERIAL_NUMBER: self._serial_number,
            CONF_MODEL_NAME: self._model_name,
        }
        return self.async_create_entry(title=self._title, data=data)

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered WiLight."""
        # Filter out basic information
        if (
            not discovery_info.ssdp_location
            or ssdp.ATTR_UPNP_MANUFACTURER not in discovery_info.upnp
            or ssdp.ATTR_UPNP_SERIAL not in discovery_info.upnp
            or ssdp.ATTR_UPNP_MODEL_NAME not in discovery_info.upnp
            or ssdp.ATTR_UPNP_MODEL_NUMBER not in discovery_info.upnp
        ):
            return self.async_abort(reason="not_wilight_device")
        # Filter out non-WiLight devices
        if discovery_info.upnp[ssdp.ATTR_UPNP_MANUFACTURER] != WILIGHT_MANUFACTURER:
            return self.async_abort(reason="not_wilight_device")

        host = urlparse(discovery_info.ssdp_location).hostname
        serial_number = discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL]
        model_name = discovery_info.upnp[ssdp.ATTR_UPNP_MODEL_NAME]

        if not self._wilight_update(host, serial_number, model_name):
            return self.async_abort(reason="not_wilight_device")

        # Check if all components of this WiLight are allowed in this version of the HA integration
        component_ok = all(
            wilight_component in ALLOWED_WILIGHT_COMPONENTS
            for wilight_component in self._wilight_components
        )

        if not component_ok:
            return self.async_abort(reason="not_supported_device")

        await self.async_set_unique_id(self._serial_number)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context["title_placeholders"] = {"name": self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Handle user-confirmation of discovered WiLight."""
        if user_input is not None:
            return self._get_entry()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._title,
                "components": self._components_text,
            },
            errors={},
        )
