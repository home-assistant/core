"""Config flow for Fujitsu IR integration."""

from typing import Any, override

import probatio

from homeassistant.components.climate import HVACMode
from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PROTOCOL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    PROTOCOL_EXTENDED,
    PROTOCOL_STANDARD,
)

_HVAC_MODE_OPTIONS = [
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.HEAT_COOL,
]
_DEFAULT_HVAC_MODES = [HVACMode.COOL, HVACMode.DRY]

_PROTOCOL_OPTIONS = [PROTOCOL_STANDARD, PROTOCOL_EXTENDED]


@callback
def _user_schema(hass: HomeAssistant) -> probatio.Schema:
    """Return the emitter/receiver/mode selection schema."""
    return probatio.Schema(
        {
            probatio.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_emitters(hass),
                )
            ),
            probatio.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN,
                    include_entities=async_get_receivers(hass),
                )
            ),
            probatio.Required(
                CONF_HVAC_MODES, default=_DEFAULT_HVAC_MODES
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
            probatio.Required(CONF_PROTOCOL, default=PROTOCOL_STANDARD): SelectSelector(
                SelectSelectorConfig(
                    options=_PROTOCOL_OPTIONS,
                    translation_key=CONF_PROTOCOL,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


class FujitsuIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Fujitsu IR."""

    VERSION = 1

    def _entity_name(self, entity_id: str) -> str:
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        return entry.name or entry.original_name or entity_id if entry else entity_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle emitter, receiver and mode selection."""
        if not async_get_emitters(self.hass):
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            emitter_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
            self._async_abort_entries_match(
                {CONF_INFRARED_EMITTER_ENTITY_ID: emitter_id}
            )
            if receiver_id := user_input.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
                self._async_abort_entries_match(
                    {CONF_INFRARED_RECEIVER_ENTITY_ID: receiver_id}
                )

            return self.async_create_entry(
                title=f"Fujitsu AC via {self._entity_name(emitter_id)}",
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=_user_schema(self.hass))
