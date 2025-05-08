"""Config flow for EnergyID integration, handling entity mapping management."""

import datetime as dt
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
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
from .const import CONF_ENERGYID_KEY, CONF_HA_ENTITY_ID, DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

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

# Define numeric state classes for sensors
NUMERIC_SENSOR_STATE_CLASSES = {
    SensorStateClass.MEASUREMENT,
    SensorStateClass.TOTAL,
    SensorStateClass.TOTAL_INCREASING,
}


@callback
def _get_suggested_entities(
    hass: HomeAssistant, current_mappings: dict[str, Any]
) -> list[str]:
    """Return entity IDs of suitable sensors, excluding already mapped ones."""
    ent_reg = er.async_get(hass)
    mapped_entity_ids = {
        data.get(CONF_HA_ENTITY_ID)
        for data in current_mappings.values()
        if isinstance(data, dict) and data.get(CONF_HA_ENTITY_ID)
    }

    suitable_entities: list[str] = []
    for entity_entry in ent_reg.entities.values():
        if not (
            entity_entry.domain == Platform.SENSOR
            and entity_entry.entity_id not in mapped_entity_ids
        ):
            continue

        is_likely_numeric_by_property = False
        entity_capabilities = entity_entry.capabilities or {}
        state_class = entity_capabilities.get("state_class")

        if state_class in NUMERIC_SENSOR_STATE_CLASSES or (
            entity_entry.device_class in SUGGESTED_DEVICE_CLASSES
            or entity_entry.original_device_class in SUGGESTED_DEVICE_CLASSES
        ):
            is_likely_numeric_by_property = True

        current_state = hass.states.get(entity_entry.entity_id)
        if current_state and current_state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            try:
                float(current_state.state)
                if entity_entry.entity_id not in suitable_entities:
                    suitable_entities.append(entity_entry.entity_id)
                continue
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "Skipping entity %s for suggestion: current state '%s' is non-numeric, despite properties",
                    entity_entry.entity_id,
                    current_state.state,
                )
                continue

        # If current state is unknown/unavailable, rely on properties
        if (
            is_likely_numeric_by_property
            and entity_entry.entity_id not in suitable_entities
        ):
            suitable_entities.append(entity_entry.entity_id)
        else:
            _LOGGER.debug(
                "Skipping entity %s for suggestion: current state is %s, and properties are not conclusively numeric",
                entity_entry.entity_id,
                current_state.state if current_state else "None",
            )
    return sorted(suitable_entities)


@callback
def _suggest_energyid_key(entity_id: str | None) -> str:
    """Suggest an appropriate EnergyID key based on the entity ID."""
    if not entity_id:
        return ""
    entity_id_lower = entity_id.lower()
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
        return "temp"
    return ""


@callback
def _create_mapping_option(
    ha_id: str, mapping_data: dict[str, str]
) -> SelectOptionDict:
    """Create a user-friendly label for the entity mapping dropdown."""
    entity_name = ha_id.split(".", 1)[-1]
    energyid_key = mapping_data.get(CONF_ENERGYID_KEY, "UNKNOWN")
    label = f"{entity_name} → {energyid_key}"
    if description := PREDEFINED_KEYS.get(energyid_key):
        label += f" ({description})"
    return SelectOptionDict(value=ha_id, label=label)


@callback
def _validate_mapping_input(
    ha_entity_id: str | None, energyid_key: str, current_mappings: dict[str, Any]
) -> dict[str, str]:
    """Validate entity mapping input and return any validation errors.

    Checks that entity ID is provided, key is not empty, has no spaces,
    and entity isn't already mapped.
    """
    errors: dict[str, str] = {}
    if not ha_entity_id:
        errors[CONF_HA_ENTITY_ID] = "entity_required"
    elif not energyid_key:
        errors[CONF_ENERGYID_KEY] = "invalid_key_empty"
    elif " " in energyid_key:
        errors[CONF_ENERGYID_KEY] = "invalid_key_spaces"
    elif ha_entity_id in current_mappings:
        errors[CONF_HA_ENTITY_ID] = "entity_already_mapped"
    return errors


async def _send_initial_state(
    hass: HomeAssistant,
    ha_entity_id: str,
    energyid_key: str,
    config_entry: EnergyIDConfigEntry,
) -> None:
    """Send the initial state of the entity to the EnergyID client."""
    entry_data = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if not entry_data:
        raise ValueError(
            f"Integration data not found in hass.data for entry {config_entry.entry_id}"
        )

    client = entry_data.get(DATA_CLIENT)
    if not client:
        raise ValueError(
            f"Webhook client not found in hass.data for entry {config_entry.entry_id}"
        )

    current_state = hass.states.get(ha_entity_id)
    if current_state and current_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        try:
            value = float(current_state.state)
            timestamp = current_state.last_updated
            # Ensure timestamp is a timezone-aware UTC datetime object
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=dt.UTC)
            elif timestamp.tzinfo != dt.UTC:
                timestamp = timestamp.astimezone(dt.UTC)

            await client.update_sensor(energyid_key, value, timestamp)
            _LOGGER.info(
                "Added new mapping: %s → %s. Queued initial state for send (Value: %s, Timestamp: %s)",
                ha_entity_id,
                energyid_key,
                value,
                timestamp.isoformat(),
            )
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Added new mapping: %s → %s, but initial send failed: Cannot convert current state '%s' to float",
                ha_entity_id,
                energyid_key,
                current_state.state,
            )
    else:
        _LOGGER.warning(
            "Added new mapping: %s → %s, but initial send failed: Current state is unknown, unavailable, or entity not found. State: %s",
            ha_entity_id,
            energyid_key,
            current_state.state if current_state else "None",
        )


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

        if user_input is not None:
            ha_entity_id_input = user_input.get(CONF_HA_ENTITY_ID)
            energyid_key = user_input.get(CONF_ENERGYID_KEY, "").strip()

            errors = _validate_mapping_input(
                ha_entity_id_input, energyid_key, current_mappings
            )

            if not errors:
                ha_entity_id_str = cast(str, ha_entity_id_input)

                new_options = dict(self.config_entry.options)
                new_options[ha_entity_id_str] = {
                    CONF_HA_ENTITY_ID: ha_entity_id_str,
                    CONF_ENERGYID_KEY: energyid_key,
                }

                try:
                    await _send_initial_state(
                        self.hass, ha_entity_id_str, energyid_key, self.config_entry
                    )
                except ValueError as e:
                    _LOGGER.error(
                        "Mapping for %s → %s added, but initial send failed: %s",
                        ha_entity_id_str,
                        energyid_key,
                        str(e),
                    )
                except Exception:
                    _LOGGER.exception(
                        "Mapping for %s → %s added, but an unexpected error occurred during initial send attempt",
                        ha_entity_id_str,
                        energyid_key,
                    )

                return self.async_create_entry(title=None, data=new_options)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HA_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(include_entities=suggested_entities)
                ),
                vol.Required(CONF_ENERGYID_KEY): TextSelector(),
            }
        )
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
        """Handle editing the EnergyID key for a sensor mapping."""
        _LOGGER.debug("Options Flow: edit_mapping step, input: %s", user_input)
        errors: dict[str, str] = {}
        ha_entity_id_to_edit = self._current_ha_entity_id
        if not ha_entity_id_to_edit:
            return self.async_abort(reason="no_mapping_selected")

        current_mapping_data = self._get_current_mappings().get(ha_entity_id_to_edit)
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
                new_options[ha_entity_id_to_edit] = {
                    CONF_HA_ENTITY_ID: ha_entity_id_to_edit,
                    CONF_ENERGYID_KEY: new_energyid_key,
                }
                _LOGGER.info(
                    "Updated mapping for %s: %s → %s",
                    ha_entity_id_to_edit,
                    current_mapping_data[CONF_ENERGYID_KEY],
                    new_energyid_key,
                )
                return self.async_create_entry(title=None, data=new_options)

        data_schema = vol.Schema({vol.Required(CONF_ENERGYID_KEY): TextSelector()})
        description_placeholders = {
            "ha_entity_id": ha_entity_id_to_edit,
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
        ha_entity_id_to_delete = self._current_ha_entity_id
        if not ha_entity_id_to_delete:
            return self.async_abort(reason="no_mapping_selected")

        current_mapping_data = self._get_current_mappings().get(ha_entity_id_to_delete)
        if not current_mapping_data:
            return self.async_abort(reason="mapping_not_found")

        if user_input is not None:
            new_options = dict(self.config_entry.options)
            if ha_entity_id_to_delete in new_options:
                del new_options[ha_entity_id_to_delete]
                _LOGGER.info(
                    "Deleted mapping for %s (EnergyID key: %s)",
                    ha_entity_id_to_delete,
                    current_mapping_data[CONF_ENERGYID_KEY],
                )
                return self.async_create_entry(title=None, data=new_options)
            return self.async_abort(reason="mapping_not_found")

        return self.async_show_form(
            step_id="delete_mapping",
            data_schema=vol.Schema({}),
            description_placeholders={
                "ha_entity_id": ha_entity_id_to_delete,
                "energyid_key": current_mapping_data[CONF_ENERGYID_KEY],
            },
            last_step=True,
        )
