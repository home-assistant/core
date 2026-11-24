"""Config flow for BenQ Projector Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DEVICE_NAME,
    DOMAIN,
)


class BenQProjectorIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for BenQ Projector Infrared."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle emitter and optional receiver selection."""
        if not (emitter_entity_ids := async_get_emitters(self.hass)):
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID]}
            )
            return self.async_create_entry(title=DEVICE_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    probatio.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=async_get_receivers(self.hass),
                        )
                    ),
                }
            ),
        )
