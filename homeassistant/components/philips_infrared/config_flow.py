"""Config flow for Philips IR integration."""

from typing import Any, override

from homeassistant.components.infrared import InfraredConsumerConfigFlow

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN


class PhilipsIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle config flow for Philips IR."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_ENTITY_ID

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        emitter_name = self._async_infrared_entity_name(
            user_input[CONF_INFRARED_ENTITY_ID]
        )
        return f"Philips TV via {emitter_name}"
