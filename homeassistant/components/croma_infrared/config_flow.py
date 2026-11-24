"""Config flow for the Croma Infrared integration."""

from typing import Any, override

from homeassistant.components.infrared import InfraredConsumerReconfigureConfigFlow

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN


class CromaIrConfigFlow(InfraredConsumerReconfigureConfigFlow, domain=DOMAIN):
    """Handle config flow for Croma IR."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_EMITTER_ENTITY_ID

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        return "Croma TV"
