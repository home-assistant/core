"""Config flow for the LED Infrared integration."""

from typing import TYPE_CHECKING, Any, override

import voluptuous as vol

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, DOMAIN, LEDIrDeviceType

DEVICE_NAMES = {
    LEDIrDeviceType.GENERIC_24_KEY: "24-key remote",
    LEDIrDeviceType.GENERIC_13_KEY: "13-key remote",
}


class LEDIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LED Infrared."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            emitter_id = user_input.get(CONF_INFRARED_ENTITY_ID)
            if emitter_id:
                self._async_abort_entries_match(
                    {
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                        CONF_INFRARED_ENTITY_ID: emitter_id,
                    }
                )

                title_entity_id = emitter_id
                if TYPE_CHECKING:
                    assert title_entity_id is not None
                ent_reg = er.async_get(self.hass)
                entry = ent_reg.async_get(title_entity_id)
                title_entity_name = (
                    entry.name or entry.original_name or title_entity_id
                    if entry
                    else title_entity_id
                )
                return self.async_create_entry(
                    title=f"LED light with {DEVICE_NAMES[LEDIrDeviceType(user_input[CONF_DEVICE_TYPE])]} via {title_entity_name}",
                    data=user_input,
                )

            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                device_type.value for device_type in LEDIrDeviceType
                            ],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.home-assistant.io/integrations/led_infrared"
            },
        )
