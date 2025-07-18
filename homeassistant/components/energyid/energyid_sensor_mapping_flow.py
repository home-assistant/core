"""Subentry flow for EnergyID integration, handling sensor mapping management."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_ENERGYID_KEY, CONF_HA_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

# --- Start of Helper Functions ---
# These functions are now included directly in the file.


@callback
def _get_suggested_entities(hass: HomeAssistant) -> list[str]:
    """Return a sorted list of suggested sensor entity IDs for mapping."""
    _LOGGER.debug("Starting _get_suggested_entities")
    ent_reg = er.async_get(hass)

    suitable_entities = []
    for entity_entry in ent_reg.entities.values():
        _LOGGER.debug("Evaluating entity: %s", entity_entry.entity_id)
        if not (
            entity_entry.domain == Platform.SENSOR and entity_entry.platform != DOMAIN
        ):
            _LOGGER.debug(
                "Skipping entity %s due to domain/platform checks",
                entity_entry.entity_id,
            )
            continue

        state_class = (entity_entry.capabilities or {}).get("state_class")
        is_likely_numeric = (
            state_class
            in (
                SensorStateClass.MEASUREMENT,
                SensorStateClass.TOTAL,
                SensorStateClass.TOTAL_INCREASING,
            )
            or entity_entry.device_class
            in (
                SensorDeviceClass.ENERGY,
                SensorDeviceClass.GAS,
                SensorDeviceClass.POWER,
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.VOLUME,
            )
            or entity_entry.original_device_class
            in (
                SensorDeviceClass.ENERGY,
                SensorDeviceClass.GAS,
                SensorDeviceClass.POWER,
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.VOLUME,
            )
        )
        current_state = hass.states.get(entity_entry.entity_id)
        if current_state and current_state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            try:
                float(current_state.state)
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "Entity %s state cannot be converted to float",
                    entity_entry.entity_id,
                )
                continue
            suitable_entities.append(entity_entry.entity_id)
            _LOGGER.debug(
                "Added entity %s to suitable entities", entity_entry.entity_id
            )
        elif (
            is_likely_numeric
            and current_state
            and current_state.state != STATE_UNAVAILABLE
        ):
            suitable_entities.append(entity_entry.entity_id)
            _LOGGER.debug(
                "Added likely numeric entity %s to suitable entities",
                entity_entry.entity_id,
            )
    _LOGGER.debug("Final list of suitable entities: %s", suitable_entities)
    return sorted(set(suitable_entities))


@callback
def _validate_mapping_input(
    ha_entity_id: str | None,
    current_mappings: set[str],
) -> dict[str, str]:
    """Validate mapping input and return errors if any."""
    errors: dict[str, str] = {}
    if not ha_entity_id:
        errors[CONF_HA_ENTITY_ID] = "entity_required"
    elif ha_entity_id in current_mappings:
        errors[CONF_HA_ENTITY_ID] = "entity_already_mapped"
    return errors


class EnergyIDSensorMappingFlowHandler(ConfigSubentryFlow):
    """Handle EnergyID sensor mapping subentry flow for adding new mappings."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step for adding a new sensor mapping."""
        errors: dict[str, str] = {}

        config_entry = self._get_entry()

        if user_input is not None:
            ha_entity_id = user_input.get(CONF_HA_ENTITY_ID)

            current_mappings = {
                sub.data[CONF_HA_ENTITY_ID] for sub in config_entry.subentries.values()
            }

            errors = _validate_mapping_input(ha_entity_id, current_mappings)

            if not errors and ha_entity_id:
                energyid_key = ha_entity_id.split(".", 1)[-1]

                subentry_data = {
                    CONF_HA_ENTITY_ID: ha_entity_id,
                    CONF_ENERGYID_KEY: energyid_key,
                }

                title = f"{ha_entity_id.split('.', 1)[-1]} → {energyid_key}"
                return self.async_create_entry(title=title, data=subentry_data)

        suggested_entities = _get_suggested_entities(self.hass)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HA_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(include_entities=suggested_entities)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
