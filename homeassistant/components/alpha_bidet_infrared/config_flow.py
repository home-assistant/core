"""Config flow for the Alpha Bidet Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import InfraredConsumerConfigFlow
from homeassistant.const import CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN, AlphaBidetModel


class AlphaBidetIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle config flow for Alpha Bidet IR."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_EMITTER_ENTITY_ID

    @override
    @callback
    def _async_infrared_schema(self) -> probatio.Schema:
        """Return the emitter and bidet model selection schema."""
        return probatio.Schema(
            {
                **self._async_infrared_entity_fields(),
                probatio.Required(CONF_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=[model.value for model in AlphaBidetModel],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        model = AlphaBidetModel(user_input[CONF_MODEL])
        return f"Alpha Bidet {model.value}"
