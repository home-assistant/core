"""Config subentry flow for EnergyID integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import CONF_ENERGYID_KEY, CONF_HA_ENTITY_ID

_LOGGER = logging.getLogger(__name__)


def get_numeric_sensor_entities(hass, config_entry: ConfigEntry) -> list[str]:
    """Return numeric sensor entity IDs."""
    ent_reg = er.async_get(hass)
    return [
        entity.entity_id
        for entity in ent_reg.entities.values()
        if entity.domain == Platform.SENSOR
    ]


class EnergyIDSubentryFlowHandler(OptionsFlow):
    """Handle the config subentry flow for EnergyID mappings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to add a mapping."""
        errors: dict[str, str] = {}
        all_sensor_entities = self.hass.states.async_entity_ids(Platform.SENSOR)

        if user_input is not None:
            ha_entity_id = user_input[CONF_HA_ENTITY_ID]
            energyid_key = user_input[CONF_ENERGYID_KEY]

            if not energyid_key or " " in energyid_key:
                errors[CONF_ENERGYID_KEY] = "invalid_key"

            if ha_entity_id in [
                sub_data.get(CONF_HA_ENTITY_ID)
                for sub_data in self.config_entry.options.values()
            ]:
                errors[CONF_HA_ENTITY_ID] = "entity_already_mapped"

            if not errors:
                new_options = dict(self.config_entry.options)
                new_options[ha_entity_id] = user_input
                return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HA_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(include_entities=all_sensor_entities)
                    ),
                    vol.Required(CONF_ENERGYID_KEY): TextSelector(),
                }
            ),
            errors=errors,
            description_placeholders={
                "entity_count": len(self.config_entry.options),
            },
        )
