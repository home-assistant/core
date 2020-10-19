"""Config flow for ozw integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_INTEGRATION_CREATED_ADDON
from .const import DOMAIN  # pylint:disable=unused-import

CONF_ADDON_DEVICE = "device"
CONF_ADDON_NETWORK_KEY = "network_key"
CONF_NETWORK_KEY = "network_key"
CONF_USB_PATH = "usb_path"
CONF_USE_ADDON = "use_addon"
TITLE = "OpenZWave"

ADDON_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USB_PATH): str,
        vol.Optional(CONF_NETWORK_KEY, default=""): str,
    }
)

ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=False): bool})


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ozw."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Set up flow instance."""
        self.addon_config = None
        self.addon_info = None
        self.network_key = None
        self.usb_path = None
        # If we install the the add-on we should uninstall it on entry unload.
        self.integration_created_addon = False

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not self.hass.components.hassio.is_hassio():
            return self._async_use_mqtt_integration()

        return await self.async_step_on_supervisor()

    @callback
    def _async_use_mqtt_integration(self):
        """Handle logic when using the MQTT integration."""
        if "mqtt" not in self.hass.config.components:
            return self.async_abort(reason="mqtt_required")

        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_USB_PATH: self.usb_path,
                CONF_NETWORK_KEY: self.network_key,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )

    async def async_step_on_supervisor(self, user_input=None):
        """Handle logic when on Supervisor host."""
        if user_input is not None:
            if user_input[CONF_USE_ADDON]:
                return await self._async_use_addon()
            return self._async_use_mqtt_integration()

        return self.async_show_form(
            step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
        )

    async def _async_use_addon(self):
        """Handle logic when using the OpenZWave add-on."""
        if await self._async_is_addon_running():
            return self._async_use_mqtt_integration()

        if await self._async_is_addon_installed():
            return await self.async_step_start_addon()

        return await self.async_step_install_addon()

    async def async_step_install_addon(self, user_input=None):
        """Ask user for add-on config and install add-on."""
        if user_input is not None:
            self.network_key = user_input[CONF_NETWORK_KEY]
            self.usb_path = user_input[CONF_USB_PATH]

            await self.hass.components.hassio.async_install_addon("core_zwave")
            self.integration_created_addon = True

            return await self.async_step_start_addon()

        return self.async_show_form(
            step_id="install_addon", data_schema=ADDON_CONFIG_SCHEMA
        )

    async def async_step_start_addon(self, user_input=None):
        """Ask for missing config and start add-on."""
        if self.usb_path is None or self.network_key is None:
            self.addon_config = await self._async_get_addon_config()

            self.usb_path = self.usb_path or self.addon_config.get(CONF_ADDON_DEVICE)
            self.network_key = self.network_key or self.addon_config.get(
                CONF_ADDON_NETWORK_KEY
            )
            data_schema = vol.Schema({})

            if not self.usb_path:
                data_schema = data_schema.extend({vol.Required(CONF_USB_PATH): str})
            if not self.network_key:
                data_schema = data_schema.extend(
                    {vol.Optional(CONF_NETWORK_KEY, default=""): str}
                )

            return self.async_show_form(step_id="start_addon", data_schema=data_schema)

        if user_input is not None:
            self.network_key = self.network_key or user_input[CONF_NETWORK_KEY]
            self.usb_path = self.usb_path or user_input[CONF_USB_PATH]

        new_addon_config = {CONF_ADDON_DEVICE: self.usb_path}
        if self.network_key:
            new_addon_config[CONF_ADDON_NETWORK_KEY] = self.network_key

        if new_addon_config != self.addon_config:
            await self._async_set_addon_config(new_addon_config)
        await self.hass.components.hassio.async_start_addon("core_zwave")

        return self._async_use_mqtt_integration()

    async def _async_get_addon_info(self):
        """Return and cache add-on info."""
        if self.addon_info is None:
            self.addon_info = await self.hass.components.hassio.async_get_addon_info(
                "core_zwave"
            )

        return self.addon_info

    async def _async_is_addon_running(self):
        """Return True if add-on is running."""
        addon_info = await self._async_get_addon_info()
        return addon_info["state"] == "started"

    async def _async_is_addon_installed(self):
        """Return True if add-on is installed."""
        addon_info = await self._async_get_addon_info()
        return addon_info["version"] is not None

    async def _async_get_addon_config(self):
        """Get add-on config."""
        addon_info = await self._async_get_addon_info()
        return addon_info["options"]

    async def _async_set_addon_config(self, config):
        """Set add-on config."""
        options = {"options": config}
        await self.hass.components.hassio.async_set_addon_options("core_zwave", options)
