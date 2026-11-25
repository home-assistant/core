"""Config flow for BenQ Projector Infrared integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
    async_get_receivers,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from . import BenQProjectorIrConfigEntry
from .const import (
    CONF_COOL_DOWN_TIME,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    CONF_WARM_UP_TIME,
    DEFAULT_COOL_DOWN_TIME,
    DEFAULT_WARM_UP_TIME,
    DEVICE_NAME,
    DOMAIN,
)

_DURATION_SELECTOR = probatio.All(
    NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=600,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement=UnitOfTime.SECONDS,
        )
    ),
    probatio.Coerce(int),
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_WARM_UP_TIME, default=DEFAULT_WARM_UP_TIME
        ): _DURATION_SELECTOR,
        probatio.Required(
            CONF_COOL_DOWN_TIME, default=DEFAULT_COOL_DOWN_TIME
        ): _DURATION_SELECTOR,
    }
)


class BenQProjectorIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for BenQ Projector Infrared."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle emitter and optional receiver selection."""
        if not (emitter_entity_ids := async_get_emitters(self.hass)):
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_INFRARED_ENTITY_ID: user_input[CONF_INFRARED_ENTITY_ID]}
            )
            return self.async_create_entry(title=DEVICE_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                    probatio.Optional(CONF_INFRARED_RECEIVER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=async_get_receivers(self.hass),
                        )
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: BenQProjectorIrConfigEntry,
    ) -> BenQProjectorIrOptionsFlow:
        """Get the options flow for this handler."""
        return BenQProjectorIrOptionsFlow()


class BenQProjectorIrOptionsFlow(OptionsFlowWithReload):
    """Handle the warm-up and cool-down times of a BenQ projector."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
