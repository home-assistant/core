"""Subentry flow for EnergyID integration, handling sensor mapping management."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_ENERGYID_KEY, CONF_HA_ENTITY_UUID, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


@callback
def _get_suggested_entities(hass: HomeAssistant) -> list[str]:
    """Return a sorted list of suggested sensor entity IDs for mapping."""
    ent_reg = er.async_get(hass)
    suitable_entities = []

    for entity_entry in ent_reg.entities.values():
        if not (
            entity_entry.domain == Platform.SENSOR and entity_entry.platform != DOMAIN
        ):
            continue

        if not hass.states.get(entity_entry.entity_id):
            continue

        state_class = (entity_entry.capabilities or {}).get("state_class")
        has_numeric_indicators = (
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

        if has_numeric_indicators:
            suitable_entities.append(entity_entry.entity_id)

    return sorted(suitable_entities)


@callback
def _validate_mapping_input(
    ha_entity_id: str | None,
    current_mappings: set[str],
    ent_reg: er.EntityRegistry,
) -> dict[str, str]:
    """Validate mapping input and return errors if any."""
    errors: dict[str, str] = {}
    if not ha_entity_id:
        errors["base"] = "entity_required"
        return errors

    # Check if entity exists
    entity_entry = ent_reg.async_get(ha_entity_id)
    if not entity_entry:
        errors["base"] = "entity_not_found"
        return errors

    # Check if entity is already mapped (by UUID)
    entity_uuid = entity_entry.id
    if entity_uuid in current_mappings:
        errors["base"] = "entity_already_mapped"

    return errors


class EnergyIDSensorMappingFlowHandler(ConfigSubentryFlow):
    """Handle EnergyID sensor mapping subentry flow for adding new mappings."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step for adding a new sensor mapping."""
        errors: dict[str, str] = {}

        config_entry = self._get_entry()
        ent_reg = er.async_get(self.hass)

        if user_input is not None:
            ha_entity_id = user_input.get("ha_entity_id")

            # Get current mappings by UUID
            current_mappings = {
                uuid
                for sub in config_entry.subentries.values()
                if (uuid := sub.data.get(CONF_HA_ENTITY_UUID)) is not None
            }

            errors = _validate_mapping_input(ha_entity_id, current_mappings, ent_reg)

            if not errors and ha_entity_id:
                # Get entity registry entry
                entity_entry = ent_reg.async_get(ha_entity_id)
                if entity_entry:
                    energyid_key = ha_entity_id.split(".", 1)[-1]

                    subentry_data = {
                        CONF_HA_ENTITY_UUID: entity_entry.id,  # Store UUID only
                        CONF_ENERGYID_KEY: energyid_key,
                    }

                    title = f"{ha_entity_id.split('.', 1)[-1]} connection to {NAME}"
                    _LOGGER.debug(
                        "Creating subentry with title='%s', data=%s",
                        title,
                        subentry_data,
                    )
                    _LOGGER.debug("Parent config entry ID: %s", config_entry.entry_id)
                    _LOGGER.debug(
                        "Creating subentry with parent: %s", self._get_entry().entry_id
                    )
                    return self.async_create_entry(title=title, data=subentry_data)
                errors["base"] = "entity_not_found"

        suggested_entities = _get_suggested_entities(self.hass)

        data_schema = vol.Schema(
            {
                vol.Required("ha_entity_id"): EntitySelector(
                    EntitySelectorConfig(include_entities=suggested_entities)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"integration_name": NAME},
        )
