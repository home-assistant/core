"""Config flow for the Persang Infrared integration."""

from typing import Any, override

from homeassistant.components.infrared import InfraredConsumerConfigFlow

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN


class PersangIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle config flow for Persang IR."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_EMITTER_ENTITY_ID

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        return "Persang speaker"
