"""Config flow for ozw integration."""
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN  # pylint:disable=unused-import

ON_SUPERVISOR_SCHEMA = vol.Schema(
    {
        vol.Required("connection"): vol.In(
            {"addon": "Add-on", "mqtt_integration": "MQTT integration"}
        )
    }
)
TITLE = "OpenZWave"


class DomainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ozw."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not self.hass.components.hassio.is_hassio():
            return await self.async_step_use_mqtt_integration()

        return await self.async_step_on_supervisor()

    async def async_step_use_mqtt_integration(self, user_input=None):
        """Handle logic when using the MQTT integration."""
        if "mqtt" not in self.hass.config.components:
            return self.async_abort(reason="mqtt_required")
        if user_input is not None:
            return self.async_create_entry(title=TITLE, data={})

        return self.async_show_form(step_id="use_mqtt_integration")

    async def async_step_on_supervisor(self, user_input=None):
        """Handle logic when on Supervisor host."""
        if user_input is not None:
            connection = user_input["connection"]
            if connection == "addon":
                return await self.async_step_use_addon()
            return await self.async_step_use_mqtt_integration()

        return self.async_show_form(
            step_id="on_supervisor", data_schema=ON_SUPERVISOR_SCHEMA
        )

    async def async_step_use_addon(self, user_input=None):
        """Handle logic when using the OpenZWave add-on."""
        pass
