"""Config flow for Flux LED/MagicLight."""
import logging

from flux_led import BulbScanner, WifiLedBulb
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FluxLED/MagicHome Integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_config: dict = None):
        """Handle configuration via YAML import."""
        _LOGGER.info("Importing configuration from YAML for flux_led.")
        config_entry = self.hass.config_entries.async_entries(DOMAIN)

        if import_config[CONF_TYPE] == "auto":
            for entry in config_entry:
                if entry.unique_id == "flux_led_auto":
                    _LOGGER.error(
                        "Your flux_led configuration has already been imported. Please remove configuration from your configuration.yaml."
                    )
                    return self.async_abort(reason="already_configured_device")

            _LOGGER.error(
                "Imported auto_add configuration for flux_led. Please remove from your configuration.yaml."
            )
            return await self.async_step_auto()

        if import_config[CONF_TYPE] == "manual":
            for entry in config_entry:
                if (
                    entry.unique_id
                    == f"{DOMAIN}_{import_config[CONF_HOST].replace('.','_')}"
                ):
                    _LOGGER.error(
                        "Your flux_led configuration for %s has already been imported. Please remove configuration from your configuration.yaml.",
                        import_config[CONF_HOST],
                    )
                    return self.async_abort(reason="already_configured_device")

            _LOGGER.error(
                "Imported flux_led configuration for %s. Please remove from your configuration.yaml.",
                import_config[CONF_HOST],
            )
            return await self.async_step_manual(import_config, source_import=True)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        config_type = None

        if user_input is not None:
            config_type = user_input[CONF_TYPE]

            return (
                await self.async_step_auto()
                if config_type == "auto"
                else await self.async_step_manual()
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE, default="auto"): vol.In(
                        {
                            "auto": "Auto Search",
                            "manual": "Manual Configuration",
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_auto(self, user_input=None):
        """Complete the auto configuration step for setup."""
        bulb_scanner = BulbScanner()
        devices = bulb_scanner.scan()

        if not devices:
            return self.async_abort(reason="no_devices_found")

        user_data = {
            CONF_TYPE: "auto",
        }
        unique_id = "flux_led_auto"
        await self.async_set_unique_id(unique_id)

        return self.async_create_entry(
            title="Auto Search",
            data=user_data,
        )

    async def async_step_manual(self, user_input=None, source_import: bool = False):
        """Complete the manual setup of an individual FluxLED Light."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME]
            ip_address = user_input[CONF_HOST]

            try:
                bulb = WifiLedBulb(ipaddr=ip_address)
                bulb.update_state()

                if bulb.mode:
                    user_data = {
                        CONF_TYPE: "manual",
                        CONF_NAME: name,
                        CONF_HOST: ip_address,
                    }
                    unique_id = f"flux_led_{ip_address.replace('.','_')}"
                    await self.async_set_unique_id(unique_id)
                    return self.async_create_entry(title=name, data=user_data)

                return self.async_abort(reason="cannot_connect")

            except BrokenPipeError:
                if source_import:
                    return self.async_abort(reason="cannot_connect")

                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )
