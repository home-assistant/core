"""Config flow for Flux LED/MagicLight."""
from flux_led import BulbScanner, WifiLedBulb
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FluxLED/MagicHome Integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        self.config_type = None

        if user_input is not None:
            self.config_type = user_input[CONF_TYPE]
            if self.config_type == "auto":
                return await self.async_step_auto()
            else:
                return await self.async_step_manual()

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
        if len(devices) == 0:
            return self.async_abort(reason="no_devices_found")
        else:
            user_data = {
                CONF_TYPE: "auto",
            }
            unique_id = "flux_led_auto"
            await self.async_set_unique_id(unique_id)
            return self.async_create_entry(
                title="Auto Search",
                data=user_data,
            )

    async def async_step_manual(self, user_input=None):
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
                else:
                    return self.async_abort(reason="cannot_connect")
            except BrokenPipeError:
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
