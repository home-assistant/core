"""Config flow for the Alpha Bidet Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN, AlphaBidetModel


@callback
def _emitter_schema(emitter_entity_ids: list[str]) -> probatio.Schema:
    """Return the infrared emitter selection schema."""
    return probatio.Schema(
        {
            probatio.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                EntitySelectorConfig(
                    domain=INFRARED_DOMAIN, include_entities=emitter_entity_ids
                )
            ),
        }
    )


class AlphaBidetIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Alpha Bidet IR."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - select IR emitter and bidet model."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_INFRARED_EMITTER_ENTITY_ID])
            self._abort_if_unique_id_configured()

            model = AlphaBidetModel(user_input[CONF_MODEL])
            return self.async_create_entry(
                title=f"Alpha Bidet {model.value}", data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_emitter_schema(emitter_entity_ids).extend(
                {
                    probatio.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=[model.value for model in AlphaBidetModel],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the infrared emitter."""
        entry = self._get_reconfigure_entry()
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            emitter_entity_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
            self._async_abort_entries_match(
                {CONF_INFRARED_EMITTER_ENTITY_ID: emitter_entity_id}
            )
            return self.async_update_reload_and_abort(
                entry, unique_id=emitter_entity_id, data_updates=user_input
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _emitter_schema(emitter_entity_ids), entry.data
            ),
        )
