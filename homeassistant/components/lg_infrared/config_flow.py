"""Config flow for LG IR integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, DOMAIN, LGDeviceType

DEVICE_TYPE_NAMES: dict[LGDeviceType, str] = {
    LGDeviceType.TV: "TV",
}


class LgIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for LG IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            entity_id = user_input[CONF_INFRARED_ENTITY_ID]
            device_type = user_input[CONF_DEVICE_TYPE]

            await self.async_set_unique_id(f"lg_ir_{device_type}_{entity_id}")
            self._abort_if_unique_id_configured()

            # Get entity name for the title
            ent_reg = er.async_get(self.hass)
            entry = ent_reg.async_get(entity_id)
            entity_name = (
                entry.name or entry.original_name or entity_id if entry else entity_id
            )
            device_type_name = DEVICE_TYPE_NAMES[LGDeviceType(device_type)]
            title = f"LG {device_type_name} via {entity_name}"

            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[device_type.value for device_type in LGDeviceType],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
        )
