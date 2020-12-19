"""Config flow for Flux LED/MagicLight."""
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for the Flux LED component."""
        return OptionsFlow(config_entry)

    async def async_step_import(self, import_config: dict = None):
        """Handle configuration via YAML import."""
        _LOGGER.info("Importing configuration from YAML for flux_led.")
        config_entry = self.hass.config_entries.async_entries(DOMAIN)

        if import_config[CONF_AUTOMATIC_ADD]:
            if config_entry:
                _LOGGER.error(
                    "Your flux_led configuration has already been imported. Please remove configuration from your configuration.yaml."
                )
                return self.async_abort(reason="already_configured_device")

            _LOGGER.error(
                "Imported auto_add configuration for flux_led. Please remove from your configuration.yaml."
            )
            return await self.async_step_user(user_input={CONF_AUTOMATIC_ADD: True})

        else:
            if config_entry:
                for device_id, device in config_entry.entry.data[CONF_DEVICES].items():
                    if device_id == import_config[CONF_HOST].replace(".", "_"):
                        _LOGGER.error(
                            "Your flux_led configuration for %s has already been imported. Please remove configuration from your configuration.yaml.",
                            import_config[CONF_HOST],
                        )
                        return self.async_abort(reason="already_configured_device")

            _LOGGER.error(
                "Imported flux_led configuration for %s. Please remove from your configuration.yaml.",
                import_config[CONF_HOST],
            )
            await self.async_step_user(
                user_input={
                    CONF_AUTOMATIC_ADD: False,
                    CONF_DEVICES: {
                        import_config[CONF_HOST].replace(".", "_"): {
                            CONF_NAME: import_config.get(
                                CONF_NAME, import_config[CONF_HOST]
                            ),
                            CONF_HOST: import_config[CONF_HOST],
                        }
                    },
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
                    devices[bulb["id"]] = bulb

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
        self._device_registry = None
        self._title = "FluxLED/MagicHome"

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
                _LOGGER.info("Will launch configuration when done.")

            if CONF_REMOVE_DEVICE in user_input:
                device_id = user_input[CONF_REMOVE_DEVICE]
                del self._config_entry.data[CONF_DEVICES][device_id]

                async_dispatcher_send(
                    self.hass, SIGNAL_REMOVE_DEVICE, {"device_id": device_id}
                )

                options_data = self._config_entry.options.copy()
                if device_id in options_data:
                    del options_data[device_id]

                return self.async_create_entry(title="", data=options_data)

            if CONF_HOST in user_input:
                device_name = (
                    user_input[CONF_NAME]
                    if CONF_NAME in user_input
                    else user_input[CONF_HOST]
                )
                device_id = user_input[CONF_HOST].replace(".", "_")
                device_data = {
                    "ipaddr": user_input[CONF_HOST],
                    CONF_NAME: device_name,
                }
                self._config_entry.data[CONF_DEVICES][device_id] = device_data

                async_dispatcher_send(
                    self.hass, SIGNAL_ADD_DEVICE, {device_id: device_data}
                )

                options_data = self._config_entry.options
                options_data[device_id] = {CONF_EFFECT_SPEED: DEFAULT_EFFECT_SPEED}
                return self.async_create_entry(title="", data=options_data)

        existing_devices = {}

        for device_id, device in self._config_entry.data[CONF_DEVICES].items():
            existing_devices[device_id] = device.get(CONF_NAME, device["ipaddr"])

        options = {
            vol.Optional(
                CONF_AUTOMATIC_ADD,
                default=self._config_entry.data[CONF_AUTOMATIC_ADD],
            ): bool,
            vol.Optional(CONF_EFFECT_SPEED, default=50): vol.All(
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
