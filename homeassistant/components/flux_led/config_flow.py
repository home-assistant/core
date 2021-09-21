"""Config flow for Flux LED/MagicLight."""
import copy
import logging

from flux_led import BulbScanner
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_CONFIGURE_DEVICE,
    CONF_DEVICES,
    CONF_EFFECT_SPEED,
    CONF_REMOVE_DEVICE,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
    SIGNAL_ADD_DEVICE,
    SIGNAL_REMOVE_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FluxLED/MagicHome Integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for the Flux LED component."""
        return OptionsFlow(config_entry)

    async def async_step_import(self, data: dict = {}):
        """Handle configuration via YAML import."""
        _LOGGER.debug("Importing configuration from YAML for flux_led")
        config_entry = self.hass.config_entries.async_entries(DOMAIN)

        if config_entry:
            _LOGGER.warning(
                "Your flux_led configuration has already been imported. Please remove configuration from your configuration.yaml"
            )
            return self.async_abort(reason="single_instance_allowed")

        _LOGGER.warning(
            "Imported auto_add configuration for flux_led. Please remove from your configuration.yaml"
        )
        return await self.async_step_user(
            user_input={
                CONF_AUTOMATIC_ADD: data[CONF_AUTOMATIC_ADD],
                CONF_DEVICES: data.get(CONF_DEVICES, {}),
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        config_entry = self.hass.config_entries.async_entries(DOMAIN)
        if config_entry:
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            devices = user_input.get(CONF_DEVICES, {})

            if user_input[CONF_AUTOMATIC_ADD]:
                scanner = BulbScanner()
                await self.hass.async_add_executor_job(scanner.scan)

                for bulb in scanner.getBulbInfo():
                    device_id = bulb["ipaddr"].replace(".", "_")
                    if not devices.get(device_id, False):
                        devices[device_id] = {
                            CONF_NAME: bulb["ipaddr"],
                            CONF_HOST: bulb["ipaddr"],
                        }

            return self.async_create_entry(
                title="FluxLED/MagicHome",
                data={
                    CONF_AUTOMATIC_ADD: user_input[CONF_AUTOMATIC_ADD],
                    CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED,
                    CONF_DEVICES: devices,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_AUTOMATIC_ADD, default=True): bool}
            ),
            errors=errors,
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle flux_led options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the flux_led options flow."""

        self._config_entry = config_entry
        self._global_options = None
        self._configure_device = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_prompt_options()

    async def async_step_prompt_options(self, user_input=None):
        """Manage the options."""

        errors = {}

        if user_input is not None:
            self._global_options = {
                CONF_AUTOMATIC_ADD: user_input[CONF_AUTOMATIC_ADD],
                CONF_EFFECT_SPEED: user_input[CONF_EFFECT_SPEED],
            }

            if CONF_CONFIGURE_DEVICE in user_input:
                self._configure_device = user_input[CONF_CONFIGURE_DEVICE]
                return await self.async_step_configure_device()

            if CONF_REMOVE_DEVICE in user_input:
                device_id = user_input[CONF_REMOVE_DEVICE]
                config_data = copy.deepcopy(dict(self._config_entry.data))
                del config_data[CONF_DEVICES][device_id]

                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=config_data
                )

                async_dispatcher_send(
                    self.hass, SIGNAL_REMOVE_DEVICE, {"device_id": device_id}
                )

                options_data = self._config_entry.options.copy()
                if device_id in options_data:
                    del options_data[device_id]
                options_data["global"] = self._global_options

                return self.async_create_entry(title="", data=options_data)

            if CONF_HOST in user_input:
                device_name = (
                    user_input[CONF_NAME]
                    if CONF_NAME in user_input
                    else user_input[CONF_HOST]
                )
                device_id = user_input[CONF_HOST].replace(".", "_")
                device_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_NAME: device_name,
                }
                config_data = copy.deepcopy(dict(self._config_entry.data))
                config_data[CONF_DEVICES][device_id] = device_data

                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=config_data
                )

                async_dispatcher_send(
                    self.hass, SIGNAL_ADD_DEVICE, {device_id: device_data}
                )

            options_data = self._config_entry.options.copy()
            options_data["global"] = self._global_options
            return self.async_create_entry(title="", data=options_data)

        existing_devices = {}

        for device_id, device in self._config_entry.data[CONF_DEVICES].items():
            existing_devices[device_id] = device.get(CONF_NAME, device[CONF_HOST])

        options = {
            vol.Optional(
                CONF_AUTOMATIC_ADD,
                default=self._config_entry.options.get("global", {}).get(
                    CONF_AUTOMATIC_ADD, self._config_entry.data[CONF_AUTOMATIC_ADD]
                ),
            ): bool,
            vol.Optional(
                CONF_EFFECT_SPEED,
                default=self._config_entry.options.get("global", {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=100),
            ),
            vol.Optional(CONF_HOST): str,
            vol.Optional(CONF_NAME): str,
            vol.Optional(CONF_CONFIGURE_DEVICE): vol.In(existing_devices),
            vol.Optional(CONF_REMOVE_DEVICE): vol.In(existing_devices),
        }

        return self.async_show_form(
            step_id="prompt_options", data_schema=vol.Schema(options), errors=errors
        )

    async def async_step_configure_device(self, user_input=None):
        """Manage the options."""

        errors = {}

        if user_input is not None:
            options_data = self._config_entry.options.copy()
            options_data[self._configure_device] = {
                CONF_EFFECT_SPEED: user_input[CONF_EFFECT_SPEED]
            }
            options_data["global"] = self._global_options
            return self.async_create_entry(title="", data=options_data)

        options = {
            vol.Required(
                CONF_EFFECT_SPEED,
                default=self._config_entry.options.get(self._configure_device, {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=100),
            )
        }

        return self.async_show_form(
            step_id="configure_device", data_schema=vol.Schema(options), errors=errors
        )
