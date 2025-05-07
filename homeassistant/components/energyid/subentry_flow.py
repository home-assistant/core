"""Config flow for EnergyID integration, handling entity mapping management."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import EnergyIDConfigEntry
from .const import CONF_ENERGYID_KEY, CONF_HA_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

# Standard EnergyID keys with descriptions
PREDEFINED_KEYS = {
    "el": "Electricity consumption (kWh)",
    "el-i": "Electricity injection (kWh)",
    "pwr": "Grid offtake power (kW)",
    "pwr-i": "Grid injection power (kW)",
    "gas": "Natural gas consumption (m³)",
    "pv": "Solar production (kWh)",
    "wind": "Wind production (kWh)",
    "bat": "Battery charging (kWh)",
    "bat-i": "Battery discharging (kWh)",
    "bat-soc": "Battery state of charge (%)",
    "heat": "Heat consumption (kWh)",
    "dw": "Drinking water (l)",
    "temp": "Temperature (°C)",
}

# Sensor device classes that work well with EnergyID
SUGGESTED_DEVICE_CLASSES = {
    SensorDeviceClass.APPARENT_POWER,
    SensorDeviceClass.AQI,
    SensorDeviceClass.BATTERY,
    SensorDeviceClass.CO,
    SensorDeviceClass.CO2,
    SensorDeviceClass.CURRENT,
    SensorDeviceClass.ENERGY,
    SensorDeviceClass.GAS,
    SensorDeviceClass.HUMIDITY,
    SensorDeviceClass.ILLUMINANCE,
    SensorDeviceClass.MOISTURE,
    SensorDeviceClass.MONETARY,
    SensorDeviceClass.NITROGEN_DIOXIDE,
    SensorDeviceClass.NITROGEN_MONOXIDE,
    SensorDeviceClass.NITROUS_OXIDE,
    SensorDeviceClass.OZONE,
    SensorDeviceClass.PM1,
    SensorDeviceClass.PM10,
    SensorDeviceClass.PM25,
    SensorDeviceClass.POWER_FACTOR,
    SensorDeviceClass.POWER,
    SensorDeviceClass.PRECIPITATION,
    SensorDeviceClass.PRECIPITATION_INTENSITY,
    SensorDeviceClass.PRESSURE,
    SensorDeviceClass.REACTIVE_POWER,
    SensorDeviceClass.SIGNAL_STRENGTH,
    SensorDeviceClass.SULPHUR_DIOXIDE,
    SensorDeviceClass.TEMPERATURE,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    SensorDeviceClass.VOLTAGE,
    SensorDeviceClass.VOLUME,
    SensorDeviceClass.WATER,
    SensorDeviceClass.WEIGHT,
    SensorDeviceClass.WIND_SPEED,
}


@callback
def _get_suggested_entities(
    hass: HomeAssistant, current_mappings: dict[str, Any]
) -> list[str]:
    """Return entity IDs of likely suitable sensors, excluding already mapped ones."""
    ent_reg = er.async_get(hass)
    mapped_entity_ids = {
        data.get(CONF_HA_ENTITY_ID)
        for data in current_mappings.values()
        if isinstance(data, dict)
    }
    return sorted(
        [
            entity.entity_id
            for entity in ent_reg.entities.values()
            if (
                entity.domain == Platform.SENSOR
                and entity.entity_id not in mapped_entity_ids
                # and (
                #     entity.device_class in SUGGESTED_DEVICE_CLASSES
                #     or entity.original_device_class in SUGGESTED_DEVICE_CLASSES
                # )
            )
        ]
    )


@callback
def _suggest_energyid_key(entity_id: str | None) -> str:
    """Suggest an appropriate EnergyID key based on the entity ID."""
    if not entity_id:
        return ""
    entity_id_lower = entity_id.lower()

    # Simple pattern matching for common sensor types
    if (
        "electricity" in entity_id_lower
        or "energy" in entity_id_lower
        or "consumption" in entity_id_lower
    ):
        return "el"
    if "solar" in entity_id_lower or "pv" in entity_id_lower:
        return "pv"
    if "gas" in entity_id_lower:
        return "gas"
    if "power" in entity_id_lower and "solar" not in entity_id_lower:
        return "pwr"
    if "battery" in entity_id_lower and "level" in entity_id_lower:
        return "bat-soc"
    if "battery" in entity_id_lower:
        return "bat"
    if "water" in entity_id_lower:
        return "dw"
    if "temperature" in entity_id_lower:
        # For temperature, suggest prefixed format
        return "temp"

    # Default to empty string if no pattern matches
    return ""


@callback
def _create_mapping_option(
    ha_id: str, mapping_data: dict[str, str]
) -> SelectOptionDict:
    """Create a user-friendly label for the mapping dropdown."""
    entity_name = ha_id.split(".", 1)[-1]
    energyid_key = mapping_data.get(CONF_ENERGYID_KEY, "UNKNOWN")
    label = f"{entity_name} → {energyid_key}"
    if description := PREDEFINED_KEYS.get(energyid_key):
        label += f" ({description})"
    return SelectOptionDict(value=ha_id, label=label)


class EnergyIDSubentryFlowHandler(OptionsFlow):
    """Handle EnergyID options flow for managing entity mappings."""

    _current_ha_entity_id: str | None = None
    config_entry: EnergyIDConfigEntry

    @callback
    def _get_current_mappings(self) -> dict[str, dict[str, str]]:
        """Get the current valid mappings from config entry options."""
        return {
            ha_id: data
            for ha_id, data in self.config_entry.options.items()
            if isinstance(data, dict)
            and isinstance(data.get(CONF_HA_ENTITY_ID), str)
            and isinstance(data.get(CONF_ENERGYID_KEY), str)
            and data[CONF_HA_ENTITY_ID] == ha_id
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: Show menu using a form."""
        _LOGGER.debug("Options Flow: init step")
        current_mappings = self._get_current_mappings()

        if user_input is not None:
            next_step_id = user_input.get("next_step")
            if next_step_id == "add_mapping":
                return await self.async_step_add_mapping()
            if next_step_id == "manage_mappings":
                return (
                    await self.async_step_manage_mappings()
                    if current_mappings
                    else self.async_abort(reason="no_mappings_to_manage")
                )
            _LOGGER.warning("Invalid next_step value: %s", next_step_id)

        options = [
            SelectOptionDict(value="add_mapping", label="Add New Sensor Mapping")
        ]
        if current_mappings:
            options.append(
                SelectOptionDict(
                    value="manage_mappings", label="View / Modify Existing Mappings"
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("next_step"): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            description_placeholders={
                "device_name": self.config_entry.title,
                "entity_count": str(len(current_mappings)),
            },
            last_step=False,
        )

    async def async_step_add_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a new sensor mapping."""
        _LOGGER.debug("Options Flow: add_mapping step, input: %s", user_input)
        errors: dict[str, str] = {}

        current_mappings = self._get_current_mappings()
        suggested_entities = _get_suggested_entities(self.hass, current_mappings)

        # Process the form
        if user_input is not None:
            ha_entity_id = user_input.get(CONF_HA_ENTITY_ID)
            energyid_key = user_input.get(CONF_ENERGYID_KEY, "").strip()

            if not ha_entity_id:
                errors[CONF_HA_ENTITY_ID] = "entity_required"
            elif not energyid_key:
                errors[CONF_ENERGYID_KEY] = "invalid_key_empty"
            elif " " in energyid_key:
                errors[CONF_ENERGYID_KEY] = "invalid_key_spaces"
            elif ha_entity_id in self.config_entry.options:
                errors[CONF_HA_ENTITY_ID] = "entity_already_mapped"

            if not errors:
                new_options = dict(self.config_entry.options)
                if ha_entity_id is not None:
                    new_options[ha_entity_id] = {
                        CONF_HA_ENTITY_ID: ha_entity_id,
                        CONF_ENERGYID_KEY: energyid_key,
                    }
                _LOGGER.info("Added new mapping: %s → %s", ha_entity_id, energyid_key)
                return self.async_create_entry(title=None, data=new_options)

        # Create the form schema - keep it simple without defaults
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HA_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(include_entities=suggested_entities)
                ),
                vol.Required(CONF_ENERGYID_KEY): TextSelector(),
            }
        )

        # Add helpful suggestions in description
        description_placeholders = {
            "suggestion_count": str(len(suggested_entities)),
            "common_keys": "Common keys: el (electricity), pv (solar), gas, temp (temperature)",
        }

        return self.async_show_form(
            step_id="add_mapping",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=True,
        )

    async def async_step_manage_mappings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show list of current mappings to select one for modification."""
        _LOGGER.debug("Options Flow: manage_mappings step, input: %s", user_input)
        current_mappings = self._get_current_mappings()
        if user_input is not None:
            selected_ha_id = user_input.get("selected_mapping")
            if selected_ha_id and selected_ha_id in current_mappings:
                self._current_ha_entity_id = selected_ha_id
                return await self.async_step_mapping_action()
            _LOGGER.warning("Invalid selection in manage_mappings: %s", selected_ha_id)
        mapping_options = [
            _create_mapping_option(ha_id, data)
            for ha_id, data in sorted(current_mappings.items())
        ]
        return self.async_show_form(
            step_id="manage_mappings",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_mapping"): SelectSelector(
                        SelectSelectorConfig(
                            options=mapping_options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            description_placeholders={"mapping_count": str(len(current_mappings))},
            last_step=False,
        )

    async def async_step_mapping_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show Edit/Delete menu for the selected mapping."""
        _LOGGER.debug("Options Flow: mapping_action step")
        ha_entity_id = self._current_ha_entity_id
        if not ha_entity_id:
            return self.async_abort(reason="no_mapping_selected")
        current_mapping_data = self._get_current_mappings().get(ha_entity_id)
        if not current_mapping_data:
            return self.async_abort(reason="mapping_not_found")
        return self.async_show_menu(
            step_id="mapping_action",
            menu_options=["edit_mapping", "delete_mapping"],
            description_placeholders={
                "ha_entity_id": ha_entity_id,
                "energyid_key": current_mapping_data[CONF_ENERGYID_KEY],
            },
        )

    async def async_step_edit_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle editing the EnergyID key."""
        _LOGGER.debug("Options Flow: edit_mapping step, input: %s", user_input)
        errors: dict[str, str] = {}
        ha_entity_id = self._current_ha_entity_id
        if not ha_entity_id:
            return self.async_abort(reason="no_mapping_selected")
        current_mapping_data = self._get_current_mappings().get(ha_entity_id)
        if not current_mapping_data:
            return self.async_abort(reason="mapping_not_found")

        if user_input is not None:
            new_energyid_key = user_input.get(CONF_ENERGYID_KEY, "").strip()
            if not new_energyid_key:
                errors[CONF_ENERGYID_KEY] = "invalid_key_empty"
            elif " " in new_energyid_key:
                errors[CONF_ENERGYID_KEY] = "invalid_key_spaces"

            if not errors:
                new_options = dict(self.config_entry.options)
                new_options[ha_entity_id] = {
                    CONF_HA_ENTITY_ID: ha_entity_id,
                    CONF_ENERGYID_KEY: new_energyid_key,
                }
                _LOGGER.info(
                    "Updated mapping for %s: %s → %s",
                    ha_entity_id,
                    current_mapping_data[CONF_ENERGYID_KEY],
                    new_energyid_key,
                )
                return self.async_create_entry(title=None, data=new_options)

        # Simple schema without defaults - this is what worked before
        data_schema = vol.Schema({vol.Required(CONF_ENERGYID_KEY): TextSelector()})

        # Show current key in description placeholders
        description_placeholders = {
            "ha_entity_id": ha_entity_id,
            "current_key": current_mapping_data[CONF_ENERGYID_KEY],
            "common_keys": "Common keys: el, pv, gas, temp, bat, water",
        }

        return self.async_show_form(
            step_id="edit_mapping",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=True,
        )

    async def async_step_delete_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and handle deletion of the selected mapping."""
        _LOGGER.debug("Options Flow: delete_mapping step")
        ha_entity_id = self._current_ha_entity_id
        if not ha_entity_id:
            return self.async_abort(reason="no_mapping_selected")
        current_mapping_data = self._get_current_mappings().get(ha_entity_id)
        if not current_mapping_data:
            return self.async_abort(reason="mapping_not_found")

        if user_input is not None:  # User confirmed deletion
            new_options = dict(self.config_entry.options)
            if ha_entity_id in new_options:
                del new_options[ha_entity_id]
                _LOGGER.info(
                    "Deleted mapping for %s (EnergyID key: %s)",
                    ha_entity_id,
                    current_mapping_data[CONF_ENERGYID_KEY],
                )
                return self.async_create_entry(title=None, data=new_options)
            return self.async_abort(reason="mapping_not_found")

        return self.async_show_form(
            step_id="delete_mapping",
            data_schema=vol.Schema({}),  # No fields, just confirmation
            description_placeholders={
                "ha_entity_id": ha_entity_id,
                "energyid_key": current_mapping_data[CONF_ENERGYID_KEY],
            },
            last_step=True,
        )
