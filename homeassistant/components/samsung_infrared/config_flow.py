"""Config flow for Samsung IR integration."""

from typing import Any, override

import probatio

from homeassistant.components.infrared import (
    DOMAIN as INFRARED_DOMAIN,
    async_get_emitters,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import entity_registry as er, translation
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    UNIQUE_ID_PREFIX,
    SamsungDeviceType,
)


class SamsungIrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Samsung IR."""

    VERSION = 1

    async def get_title(self, entity_id: str, device_type: str) -> str:
        """Generates a title for the config."""
        ent_reg = er.async_get(self.hass)
        entry = ent_reg.async_get(entity_id)
        entity_name = (
            entry.name or entry.original_name or entity_id if entry else entity_id
        )
        device_type_key = SamsungDeviceType(device_type).value
        translations = await translation.async_get_translations(
            self.hass, self.hass.config.language, "selector", {DOMAIN}
        )
        device_type_name = translations.get(
            f"component.{DOMAIN}.selector.device_type.options.{device_type_key}",
            device_type_key,
        )

        return f"Samsung {device_type_name} via {entity_name}"

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            entity_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]
            device_type = user_input[CONF_DEVICE_TYPE]

            await self.async_set_unique_id(
                f"{UNIQUE_ID_PREFIX}{device_type}_{entity_id}"
            )
            self._abort_if_unique_id_configured()

            title = await self.get_title(entity_id=entity_id, device_type=device_type)

            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                device_type.value for device_type in SamsungDeviceType
                            ],
                            translation_key=CONF_DEVICE_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(
                            domain=INFRARED_DOMAIN,
                            include_entities=emitter_entity_ids,
                        )
                    ),
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the infrared transmitter."""
        emitter_entity_ids = async_get_emitters(self.hass)
        if not emitter_entity_ids:
            return self.async_abort(reason="no_emitters")

        reconfigure_entry = self._get_reconfigure_entry()
        device_type = reconfigure_entry.data[CONF_DEVICE_TYPE]

        if user_input is not None:
            entity_id = user_input[CONF_INFRARED_EMITTER_ENTITY_ID]

            await self.async_set_unique_id(
                f"{UNIQUE_ID_PREFIX}{device_type}_{entity_id}"
            )
            if self.unique_id != reconfigure_entry.unique_id:
                self._abort_if_unique_id_configured()

            title = await self.get_title(entity_id=entity_id, device_type=device_type)

            return self.async_update_reload_and_abort(
                reconfigure_entry,
                unique_id=self.unique_id,
                title=title,
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_INFRARED_EMITTER_ENTITY_ID
                        ): EntitySelector(
                            EntitySelectorConfig(
                                domain=INFRARED_DOMAIN,
                                include_entities=emitter_entity_ids,
                            )
                        ),
                    }
                ),
                reconfigure_entry.data,
            ),
        )
