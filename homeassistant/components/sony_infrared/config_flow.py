"""Config flow for the Sony Infrared integration."""

from typing import Any, override

import probatio

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

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, DOMAIN, SonyDeviceType

DEVICE_TYPE_NAMES: dict[SonyDeviceType, str] = {
    SonyDeviceType.TV: "TV",
}


class SonyIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony Infrared."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device type and emitter selection."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_emitters")

        if user_input is not None:
            device_type = SonyDeviceType(user_input[CONF_DEVICE_TYPE])
            emitter_id = user_input[CONF_INFRARED_ENTITY_ID]
            self._async_abort_entries_match(
                {CONF_DEVICE_TYPE: device_type, CONF_INFRARED_ENTITY_ID: emitter_id}
            )
            return self.async_create_entry(
                title=(
                    f"Sony {DEVICE_TYPE_NAMES[device_type]} via "
                    f"{self._entity_name(emitter_id)}"
                ),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                device_type.value for device_type in SonyDeviceType
                            ],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Required(CONF_INFRARED_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
        )

    def _entity_name(self, entity_id: str) -> str:
        """Return the name of an infrared entity for the entry title."""
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is None:
            return entity_id
        return entry.name or entry.original_name or entity_id
