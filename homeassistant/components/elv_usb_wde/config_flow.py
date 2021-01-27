"""Config flow for ELV USB-WDE1."""
import voluptuous as vol

from homeassistant import config_entries

from .const import DEFAULT_DEVICE, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class DeviceConfigFlow(config_entries.ConfigFlow):
    """Configure the ELV USB WDE1 integration."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # (this is not implemented yet)
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Allow the user to configure the device path."""
        data_schema = {
            vol.Optional("device", default=DEFAULT_DEVICE): str,
        }

        if user_input is not None:
            return self.async_create_entry(
                title="USB WDE Device Path",
                data={"device": user_input["device"]},
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))
