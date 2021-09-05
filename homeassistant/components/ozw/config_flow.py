"""Config flow for ozw integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_INTEGRATION_CREATED_ADDON, CONF_USE_ADDON, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ADDON_DEVICE = "device"
CONF_ADDON_NETWORK_KEY = "network_key"
CONF_NETWORK_KEY = "network_key"
CONF_USB_PATH = "usb_path"
TITLE = "OpenZWave"

ON_SUPERVISOR_SCHEMA = vol.Schema({vol.Optional(CONF_USE_ADDON, default=False): bool})


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ozw."""

    VERSION = 1

    def __init__(self):
        """Set up flow instance."""
        self.addon_config = None
        self.network_key = None
        self.usb_path = None
        self.use_addon = False
        # If we install the add-on we should uninstall it on entry remove.
        self.integration_created_addon = False
        self.install_task = None

    async def async_step_import(self, data):
        """Handle imported data.

        This step will be used when importing data during zwave to ozw migration.
        """
        self.network_key = data.get(CONF_NETWORK_KEY)
        self.usb_path = data.get(CONF_USB_PATH)
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Set a unique_id to make sure discovery flow is aborted on progress.
        await self.async_set_unique_id(DOMAIN, raise_on_progress=False)

        if not self.hass.components.hassio.is_hassio():
            return self._async_use_mqtt_integration()

        return await self.async_step_on_supervisor()

    async def async_step_hassio(self, discovery_info):
        """Receive configuration from add-on discovery info.

        This flow is triggered by the OpenZWave add-on.
        """
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm the add-on discovery."""
        if user_input is not None:
            return await self.async_step_on_supervisor(
                user_input={CONF_USE_ADDON: True}
            )

        return self.async_show_form(step_id="hassio_confirm")

    def _async_create_entry_from_vars(self):
        """Return a config entry for the flow."""
        return self.async_create_entry(
            title=TITLE,
            data={
                CONF_USB_PATH: self.usb_path,
                CONF_NETWORK_KEY: self.network_key,
                CONF_USE_ADDON: self.use_addon,
                CONF_INTEGRATION_CREATED_ADDON: self.integration_created_addon,
            },
        )

    @callback
    def _async_use_mqtt_integration(self):
        """Handle logic when using the MQTT integration.

        This is the entry point for the logic that is needed
        when this integration will depend on the MQTT integration.
        """
        mqtt_entries = self.hass.config_entries.async_entries("mqtt")
        if (
            not mqtt_entries
            or mqtt_entries[0].state is not config_entries.ConfigEntryState.LOADED
        ):
            return self.async_abort(reason="mqtt_required")
        return self._async_create_entry_from_vars()

    async def async_step_on_supervisor(self, user_input=None):
        """Handle logic when on Supervisor host."""
        if user_input is None:
            return self.async_show_form(
                step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
            )
        if not user_input[CONF_USE_ADDON]:
            return self._async_create_entry_from_vars()

        self.use_addon = True

        if await self._async_is_addon_running():
            addon_config = await self._async_get_addon_config()
            self.usb_path = addon_config[CONF_ADDON_DEVICE]
            self.network_key = addon_config.get(CONF_ADDON_NETWORK_KEY, "")
            return self._async_create_entry_from_vars()

        if await self._async_is_addon_installed():
            return await self.async_step_start_addon()

        return await self.async_step_install_addon()

    async def async_step_install_addon(self, user_input=None):
        """Install OpenZWave add-on."""
        if not self.install_task:
            self.install_task = self.hass.async_create_task(self._async_install_addon())
            return self.async_show_progress(
                step_id="install_addon", progress_action="install_addon"
            )

        try:
            await self.install_task
        except self.hass.components.hassio.HassioAPIError as err:
            _LOGGER.error("Failed to install OpenZWave add-on: %s", err)
            return self.async_show_progress_done(next_step_id="install_failed")

        self.integration_created_addon = True

        return self.async_show_progress_done(next_step_id="start_addon")

    async def async_step_install_failed(self, user_input=None):
        """Add-on installation failed."""
        return self.async_abort(reason="addon_install_failed")

    async def async_step_start_addon(self, user_input=None):
        """Ask for config and start OpenZWave add-on."""
        if self.addon_config is None:
            self.addon_config = await self._async_get_addon_config()

        errors = {}

        if user_input is not None:
            self.network_key = user_input[CONF_NETWORK_KEY]
            self.usb_path = user_input[CONF_USB_PATH]

            new_addon_config = {
                CONF_ADDON_DEVICE: self.usb_path,
                CONF_ADDON_NETWORK_KEY: self.network_key,
            }

            if new_addon_config != self.addon_config:
                await self._async_set_addon_config(new_addon_config)

            try:
                await self.hass.components.hassio.async_start_addon("core_zwave")
            except self.hass.components.hassio.HassioAPIError as err:
                _LOGGER.error("Failed to start OpenZWave add-on: %s", err)
                errors["base"] = "addon_start_failed"
            else:
                return self._async_create_entry_from_vars()

        usb_path = self.addon_config.get(CONF_ADDON_DEVICE, self.usb_path or "")
        network_key = self.addon_config.get(
            CONF_ADDON_NETWORK_KEY, self.network_key or ""
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PATH, default=usb_path): str,
                vol.Optional(CONF_NETWORK_KEY, default=network_key): str,
            }
        )

        return self.async_show_form(
            step_id="start_addon", data_schema=data_schema, errors=errors
        )

    async def _async_get_addon_info(self):
        """Return and cache OpenZWave add-on info."""
        try:
            addon_info = await self.hass.components.hassio.async_get_addon_info(
                "core_zwave"
            )
        except self.hass.components.hassio.HassioAPIError as err:
            _LOGGER.error("Failed to get OpenZWave add-on info: %s", err)
            raise AbortFlow("addon_info_failed") from err

        return addon_info

    async def _async_is_addon_running(self):
        """Return True if OpenZWave add-on is running."""
        addon_info = await self._async_get_addon_info()
        return addon_info["state"] == "started"

    async def _async_is_addon_installed(self):
        """Return True if OpenZWave add-on is installed."""
        addon_info = await self._async_get_addon_info()
        return addon_info["version"] is not None

    async def _async_get_addon_config(self):
        """Get OpenZWave add-on config."""
        addon_info = await self._async_get_addon_info()
        return addon_info["options"]

    async def _async_set_addon_config(self, config):
        """Set OpenZWave add-on config."""
        options = {"options": config}
        try:
            await self.hass.components.hassio.async_set_addon_options(
                "core_zwave", options
            )
        except self.hass.components.hassio.HassioAPIError as err:
            _LOGGER.error("Failed to set OpenZWave add-on config: %s", err)
            raise AbortFlow("addon_set_config_failed") from err

    async def _async_install_addon(self):
        """Install the OpenZWave add-on."""
        try:
            await self.hass.components.hassio.async_install_addon("core_zwave")
        finally:
            # Continue the flow after show progress when the task is done.
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
            )
