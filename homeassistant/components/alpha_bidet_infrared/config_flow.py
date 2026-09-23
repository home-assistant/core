"""Config flow for the Alpha Bidet Infrared integration."""

from typing import Any, override

from infrared_protocols.codes.alpha_bidet.models import AlphaBidetModel
import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN


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
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    probatio.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=[model.value for model in AlphaBidetModel],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
