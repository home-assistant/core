"""Config flow for the Ceiling Fan Infrared integration."""

from typing import Any, override

from homeassistant.components.infrared import InfraredConsumerConfigFlow

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN


class CeilingFanIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ceiling Fan Infrared."""

    INFRARED_EMITTER_KEY = CONF_INFRARED_ENTITY_ID

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        emitter_name = self._async_infrared_entity_name(
            user_input[CONF_INFRARED_ENTITY_ID]
        )
        return f"Ceiling fan via {emitter_name}"
