"""Config flow for Edifier infrared integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_COMMAND_SET,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    MODEL_TO_COMMAND_SET,
    EdifierModel,
)


class EdifierIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Edifier IR."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - select IR entity and speaker model."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            infrared_entity_id = user_input[CONF_INFRARED_ENTITY_ID]
            model = EdifierModel(user_input[CONF_MODEL])
            device_type = MODEL_TO_COMMAND_SET[model]

            await self.async_set_unique_id(f"{device_type}_{infrared_entity_id}")
            self._abort_if_unique_id_configured()

            entity_name = infrared_entity_id
            if state := self.hass.states.get(infrared_entity_id):
                entity_name = state.name or infrared_entity_id

            return self.async_create_entry(
                title=f"Edifier {model.value} via {entity_name}",
                data={
                    CONF_INFRARED_ENTITY_ID: infrared_entity_id,
                    CONF_MODEL: model.value,
                    CONF_COMMAND_SET: device_type.value,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN, include_entities=emitter_entity_ids
                        )
                    ),
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=[model.value for model in EdifierModel],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
