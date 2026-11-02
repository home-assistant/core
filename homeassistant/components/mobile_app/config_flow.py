"""Config flow for Mobile App."""

from typing import Any, override
import uuid

from homeassistant.components import person
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.helpers import entity_registry as er

from .const import ATTR_APP_ID, ATTR_DEVICE_NAME, CONF_USER_ID, DOMAIN
from .util import async_retire_webhook


class MobileAppFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Mobile App config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        placeholders = {
            "apps_url": "https://www.home-assistant.io/integrations/mobile_app/#apps"
        }

        return self.async_abort(
            reason="install_app", description_placeholders=placeholders
        )

    async def async_step_registration(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized during registration."""
        if ATTR_DEVICE_ID in user_input:
            # Unique ID is combi of app + device ID.
            await self.async_set_unique_id(
                f"{user_input[ATTR_APP_ID]}-{user_input[ATTR_DEVICE_ID]}"
            )
        else:
            user_input[ATTR_DEVICE_ID] = str(uuid.uuid4()).replace("-", "")

        # Register device tracker entity and add to person registering app
        entity_registry = er.async_get(self.hass)
        devt_entry = entity_registry.async_get_or_create(
            "device_tracker",
            DOMAIN,
            user_input[ATTR_DEVICE_ID],
            object_id_base=user_input[ATTR_DEVICE_NAME],
        )
        await person.async_add_user_device_tracker(
            self.hass, user_input[CONF_USER_ID], devt_entry.entity_id
        )

        if self.unique_id is not None and (
            existing_entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, self.unique_id
            )
        ):
            return await self._async_update_registration(existing_entry, user_input)

        return self.async_create_entry(
            title=user_input[ATTR_DEVICE_NAME], data=user_input
        )

    async def _async_update_registration(
        self, entry: ConfigEntry, registration: dict[str, Any]
    ) -> ConfigFlowResult:
        """Update the entry of an app which registers again."""
        # Every registration gets a new webhook ID, so the entry is unloaded
        # while its data still has the old one
        await self.hass.config_entries.async_unload(entry.entry_id)
        await async_retire_webhook(self.hass, entry)

        # Sensor unique IDs are prefixed with the webhook ID
        old_prefix = f"{entry.data[CONF_WEBHOOK_ID]}_"
        new_prefix = f"{registration[CONF_WEBHOOK_ID]}_"
        entity_registry = er.async_get(self.hass)
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.unique_id.startswith(old_prefix):
                entity_registry.async_update_entity(
                    entity.entity_id,
                    new_unique_id=new_prefix
                    + entity.unique_id.removeprefix(old_prefix),
                )

        self.hass.config_entries.async_update_entry(
            entry, title=registration[ATTR_DEVICE_NAME], data=registration
        )
        if entry.state is ConfigEntryState.NOT_LOADED and not entry.disabled_by:
            await self.hass.config_entries.async_setup(entry.entry_id)
        return self.async_abort(reason="registration_updated")
