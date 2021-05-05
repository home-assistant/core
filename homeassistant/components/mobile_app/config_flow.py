"""Config flow for Mobile App."""
import uuid

from homeassistant import config_entries
from homeassistant.components import person
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.helpers import entity_registry as er

from .const import ATTR_APP_ID, ATTR_DEVICE_NAME, CONF_USER_ID, DOMAIN


class MobileAppFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Mobile App config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        placeholders = {
            "apps_url": "https://www.home-assistant.io/integrations/mobile_app/#apps"
        }

        return self.async_abort(
            reason="install_app", description_placeholders=placeholders
        )

    async def async_step_registration(self, user_input=None):
        """Handle a flow initialized during registration."""
        if ATTR_DEVICE_ID in user_input:
            # Unique ID is combi of app + device ID.
            await self.async_set_unique_id(
                f"{user_input[ATTR_APP_ID]}-{user_input[ATTR_DEVICE_ID]}"
            )
        else:
            user_input[ATTR_DEVICE_ID] = str(uuid.uuid4()).replace("-", "")

        # Register device tracker entity and add to person registering app
        entity_registry = await er.async_get_registry(self.hass)
        devt_entry = entity_registry.async_get_or_create(
            "device_tracker",
            DOMAIN,
            user_input[ATTR_DEVICE_ID],
            suggested_object_id=user_input[ATTR_DEVICE_NAME],
        )
        await person.async_add_user_device_tracker(
            self.hass, user_input[CONF_USER_ID], devt_entry.entity_id
        )

        return self.async_create_entry(
            title=user_input[ATTR_DEVICE_NAME], data=user_input
        )
