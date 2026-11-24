"""Config flow for Marantz IR integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import InfraredConsumerConfigFlow
from homeassistant.const import CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN, MODELS


class MarantzIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle config flow for Marantz IR."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_EMITTER_ENTITY_ID

    @override
    @callback
    def _async_infrared_schema(self) -> probatio.Schema:
        """Return the model and emitter selection schema."""
        model_options = [
            SelectOptionDict(value=slug, label=model.name)
            for slug, model in MODELS.items()
        ]
        return probatio.Schema(
            {
                probatio.Required(CONF_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=model_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                **self._async_infrared_entity_fields(),
            }
        )

    @override
    @callback
    def _async_infrared_match_dict(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Return the model, so each model can use the same emitter."""
        return {CONF_MODEL: user_input[CONF_MODEL]}

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        return MODELS[user_input[CONF_MODEL]].name
