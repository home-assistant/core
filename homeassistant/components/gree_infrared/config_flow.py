"""Config flow for Gree IR integration."""

from typing import Any, override

import probatio

from homeassistant.components.climate import HVACMode
from homeassistant.components.infrared import InfraredConsumerConfigFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DEFAULT_HVAC_MODES,
    DOMAIN,
)

_HVAC_MODE_OPTIONS = [
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.AUTO,
]


class GreeIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle config flow for Gree IR."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_EMITTER_ENTITY_ID
    INFRARED_RECEIVER_KEY = CONF_INFRARED_RECEIVER_ENTITY_ID

    @override
    @callback
    def _async_infrared_schema(self) -> probatio.Schema:
        """Return the emitter/receiver/mode selection schema."""
        return probatio.Schema(
            {
                **self._async_infrared_entity_fields(),
                probatio.Required(
                    CONF_HVAC_MODES, default=DEFAULT_HVAC_MODES
                ): probatio.All(
                    SelectSelector(
                        SelectSelectorConfig(
                            options=[mode.value for mode in _HVAC_MODE_OPTIONS],
                            translation_key=CONF_HVAC_MODES,
                            mode=SelectSelectorMode.LIST,
                            multiple=True,
                        )
                    ),
                    probatio.Length(min=1, msg="no_hvac_modes"),
                ),
            }
        )

    @override
    @callback
    def _async_infrared_reconfigure_schema(self) -> probatio.Schema:
        """Return the emitter/receiver/mode selection schema."""
        return self._async_infrared_schema()

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        emitter_name = self._async_infrared_entity_name(
            user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
        )
        return f"Gree AC via {emitter_name}"
