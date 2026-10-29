"""Config flow for the SilverCrest Infrared integration."""

from typing import TYPE_CHECKING, Any, override

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

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DEVICE_NAMES,
    DOMAIN,
    SilverCrestIrDeviceType,
)


class SilverCrestIfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SilverCrest Infrared."""

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
                self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
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
                    title=f"{DEVICE_NAMES[SilverCrestIrDeviceType(user_input[CONF_DEVICE_TYPE])]} via {title_entity_name}",
                    data=user_input,
                )

            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_DEVICE_TYPE): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    device_type.value
                                    for device_type in SilverCrestIrDeviceType
                                ],
                                translation_key=CONF_DEVICE_TYPE,
                                mode=SelectSelectorMode.DROPDOWN,
                                sort=True,
                            )
                        ),
                        probatio.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                            EntitySelectorConfig(
                                domain=INFRARED_DOMAIN,
                                include_entities=emitter_entity_ids,
                            )
                        ),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow."""
        errors: dict[str, str] = {}

        entry = self._get_reconfigure_entry()

        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_infrared_entities")

        if user_input is not None:
            emitter_id = user_input.get(CONF_INFRARED_ENTITY_ID)
            if emitter_id:
                self._async_abort_entries_match({CONF_INFRARED_ENTITY_ID: emitter_id})
                return self.async_update_reload_and_abort(
                    entry,
                    data={CONF_DEVICE_TYPE: entry.data[CONF_DEVICE_TYPE], **user_input},
                )

            errors["base"] = "missing_infrared_entity"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Optional(CONF_INFRARED_ENTITY_ID): EntitySelector(
                            EntitySelectorConfig(
                                domain=INFRARED_DOMAIN,
                                include_entities=emitter_entity_ids,
                            )
                        )
                    }
                ),
                entry.data,
            ),
            errors=errors,
        )
