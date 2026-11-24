"""Config flow for Dyson Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import InfraredConsumerConfigFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)

DEVICE_TYPE_NAMES: dict[DysonDeviceType, str] = {
    DysonDeviceType.FAN: "Fan",
}


class DysonIrConfigFlow(InfraredConsumerConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dyson Infrared."""

    VERSION = 1
    INFRARED_EMITTER_KEY = CONF_INFRARED_EMITTER_ENTITY_ID

    @override
    @callback
    def _async_infrared_schema(self) -> probatio.Schema:
        """Return the device type and emitter selection schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_DEVICE_TYPE): SelectSelector(
                    SelectSelectorConfig(
                        options=[device_type.value for device_type in DysonDeviceType],
                        translation_key=CONF_DEVICE_TYPE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                **self._async_infrared_entity_fields(),
            }
        )

    @override
    @callback
    def _async_infrared_match_dict(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Return the device type, so each device type can use the same emitter."""
        return {CONF_DEVICE_TYPE: DysonDeviceType(user_input[CONF_DEVICE_TYPE])}

    @override
    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        device_type = DysonDeviceType(user_input[CONF_DEVICE_TYPE])
        emitter_name = self._async_infrared_entity_name(
            user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
        )
        return f"Dyson {DEVICE_TYPE_NAMES[device_type]} via {emitter_name}"
