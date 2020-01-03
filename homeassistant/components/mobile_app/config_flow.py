"""Config flow for Mobile App."""
from homeassistant import config_entries

from .const import ATTR_APP_ID, ATTR_DEVICE_NAME, ATTR_MODEL_ID, DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class MobileAppFlowHandler(config_entries.ConfigFlow):
    """Handle a Mobile App config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        placeholders = {
            "apps_url": "https://www.home-assistant.io/components/mobile_app/#apps"
        }

        return self.async_abort(
            reason="install_app", description_placeholders=placeholders
        )

    async def async_step_registration(self, user_input=None):
        """Handle a flow initialized during registration."""
        model_id = user_input.get(ATTR_MODEL_ID)

        if model_id is not None:
            await self.async_set_unique_id(f"{user_input[ATTR_APP_ID]}-{model_id}")

        return self.async_create_entry(
            title=user_input[ATTR_DEVICE_NAME], data=user_input
        )
