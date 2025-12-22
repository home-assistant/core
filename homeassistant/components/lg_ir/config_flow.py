"""Config flow for LG IR integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import InfraredProtocolType, async_get_entities
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.typing import UndefinedType

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN


class LgIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for LG IR."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        entities = async_get_entities(self.hass, protocols={InfraredProtocolType.NEC})
        if not entities:
            return self.async_abort(reason="no_emitters")

        entity_options = {
            entity.entity_id: entity.name
            if entity.name and not isinstance(entity.name, UndefinedType)
            else entity.entity_id
            for entity in entities
        }

        if user_input is not None:
            entity_id = user_input[CONF_INFRARED_ENTITY_ID]

            if entity_id in entity_options:
                await self.async_set_unique_id(f"lg_ir_{entity_id}")
                self._abort_if_unique_id_configured()

                entity_name = entity_options[entity_id]
                title = f"LG TV via {entity_name}"

                return self.async_create_entry(title=title, data=user_input)

            errors["base"] = "invalid_emitter"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INFRARED_ENTITY_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=entity_id, label=name)
                                for entity_id, name in entity_options.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )
