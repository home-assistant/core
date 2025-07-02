"""Subentry flow for EnergyID integration, handling sensor mapping management."""

import datetime as dt
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
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
NUMERIC_SENSOR_STATE_CLASSES = {
    SensorStateClass.MEASUREMENT,
    SensorStateClass.TOTAL,
    SensorStateClass.TOTAL_INCREASING,
}


@callback
def _get_suggested_entities(
    hass: HomeAssistant, current_mappings: dict[str, Any]
) -> list[str]:
    """Return a sorted list of suggested sensor entity IDs for mapping."""
    ent_reg = er.async_get(hass)
    mapped_entity_ids = {
        data.get(CONF_HA_ENTITY_ID)
        for data in current_mappings.values()
        if isinstance(data, dict)
    }
    suitable_entities = []
    for entity_entry in ent_reg.entities.values():
        if not (
            entity_entry.domain == Platform.SENSOR
            and entity_entry.entity_id not in mapped_entity_ids
            and entity_entry.platform != DOMAIN
        ):
            continue
        state_class = (entity_entry.capabilities or {}).get("state_class")
        is_likely_numeric = (
            state_class in NUMERIC_SENSOR_STATE_CLASSES
            or entity_entry.device_class in SUGGESTED_DEVICE_CLASSES
            or entity_entry.original_device_class in SUGGESTED_DEVICE_CLASSES
        )
        current_state = hass.states.get(entity_entry.entity_id)
        if current_state and current_state.state not in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            try:
                float(current_state.state)
                suitable_entities.append(entity_entry.entity_id)
            except (ValueError, TypeError):
                continue
        elif is_likely_numeric:
            suitable_entities.append(entity_entry.entity_id)
    return sorted(set(suitable_entities))


@callback
def _create_mapping_option(
    ha_id: str, mapping_data: dict[str, str]
) -> SelectOptionDict:
    """Create a select option for a mapping."""
    entity_name = ha_id.split(".", 1)[-1]
    key = mapping_data.get(CONF_ENERGYID_KEY, "UNKNOWN")
    label = f"{entity_name} → {key}"
    if desc := PREDEFINED_KEYS.get(key):
        label += f" ({desc})"
    return SelectOptionDict(value=ha_id, label=label)


@callback
def _validate_mapping_input(
    ha_entity_id: str | None,
    energyid_key: str,
    current_mappings: dict[str, Any],
    is_editing: bool = False,
) -> dict[str, str]:
    """Validate mapping input and return errors if any."""
    errors: dict[str, str] = {}
    if not ha_entity_id:
        errors[CONF_HA_ENTITY_ID] = "entity_required"
    elif not energyid_key:
        errors[CONF_ENERGYID_KEY] = "invalid_key_empty"
    elif " " in energyid_key:
        errors[CONF_ENERGYID_KEY] = "invalid_key_spaces"
    elif not is_editing and ha_entity_id in current_mappings:
        errors[CONF_HA_ENTITY_ID] = "entity_already_mapped"
    return errors


async def _send_initial_state(
    hass: HomeAssistant, ha_entity_id: str, energyid_key: str, config_entry: ConfigEntry
) -> None:
    """Send the initial state of the mapped entity to EnergyID."""
    current_state = hass.states.get(ha_entity_id)

    if not current_state or current_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        _LOGGER.warning(
            "Mapping %s → %s: Initial send skipped, state is %s",
            ha_entity_id,
            energyid_key,
            current_state.state if current_state else "None",
        )
        return

    try:
        value = float(current_state.state)
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Mapping %s → %s: Initial send failed, cannot convert state '%s' to float",
            ha_entity_id,
            energyid_key,
            current_state.state,
        )
        return

    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    timestamp = current_state.last_updated

    timestamp_utc = (
        timestamp.astimezone(dt.UTC)
        if timestamp.tzinfo
        else timestamp.replace(tzinfo=dt.UTC)
    )

    try:
        await client.update_sensor(energyid_key, value, timestamp_utc)
        _LOGGER.debug(
            "Mapping %s → %s: Initial state sent successfully",
            ha_entity_id,
            energyid_key,
        )
    except Exception:
        _LOGGER.exception(
            "Mapping %s → %s: Initial send failed with an unexpected API exception",
            ha_entity_id,
            energyid_key,
        )


class EnergyIDSensorMappingFlowHandler(ConfigSubentryFlow):
    """Handle EnergyID sensor mapping subentry flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the sensor mapping subentry flow handler."""
        self.config_entry = config_entry
        self._current_ha_entity_id: str | None = None

    @callback
    def _get_current_mappings(self) -> dict[str, dict[str, str]]:
        """Get current valid mappings from parent config entry's options."""
        return {
            ha_id: data
            for ha_id, data in self.config_entry.options.items()
            if isinstance(data, dict) and data.get(CONF_HA_ENTITY_ID) == ha_id
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """First step for subentry flow: Show menu or proceed."""
        current_mappings = self._get_current_mappings()
        if user_input is not None:
            if (next_step := user_input.get("next_step")) == "add_mapping":
                return await self.async_step_add_mapping()
            if next_step == "manage_mappings":
                return (
                    await self.async_step_manage_mappings()
                    if current_mappings
                    else self.async_abort(reason="no_mappings_to_manage")
                )

        options_list = [
            SelectOptionDict(value="add_mapping", label="Add New Sensor Mapping")
        ]
        if current_mappings:
            options_list.append(
                SelectOptionDict(
                    value="manage_mappings", label="View / Modify Existing Mappings"
                )
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("next_step"): SelectSelector(
                        SelectSelectorConfig(
                            options=options_list, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            description_placeholders={
                "device_name": self.config_entry.title,
                "entity_count": str(len(current_mappings)),
            },
        )

    async def async_step_add_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle adding a new sensor mapping."""
        errors: dict[str, str] = {}
        if user_input is not None:
            ha_entity_id = user_input.get(CONF_HA_ENTITY_ID)
            energyid_key = user_input.get(CONF_ENERGYID_KEY, "").strip()
            errors = _validate_mapping_input(
                ha_entity_id, energyid_key, self._get_current_mappings()
            )

            if not errors and ha_entity_id:
                new_options = dict(self.config_entry.options)
                new_options[ha_entity_id] = {
                    CONF_HA_ENTITY_ID: ha_entity_id,
                    CONF_ENERGYID_KEY: energyid_key,
                }
                await _send_initial_state(
                    self.hass, ha_entity_id, energyid_key, self.config_entry
                )
                title = f"{ha_entity_id.split('.', 1)[-1]} → {energyid_key}"
                return self.async_create_entry(title=title, data=new_options)

        suggested_entities = _get_suggested_entities(
            self.hass, self._get_current_mappings()
        )
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HA_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(include_entities=suggested_entities)
                ),
                vol.Required(CONF_ENERGYID_KEY): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="add_mapping",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "suggestion_count": str(len(suggested_entities)),
                "common_keys": "Common: el, pv, gas, temp",
            },
        )

    async def async_step_manage_mappings(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show list of mappings to select for modification."""
        selected_id = user_input.get("selected_mapping") if user_input else None
        if selected_id:
            self._current_ha_entity_id = selected_id
            return await self.async_step_mapping_action()

        current_mappings = self._get_current_mappings()
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
        )

    async def async_step_mapping_action(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show Edit/Delete menu for the selected mapping."""
        if not (ha_entity_id := self._current_ha_entity_id) or not (
            data := self._get_current_mappings().get(ha_entity_id)
        ):
            return self.async_abort(reason="mapping_not_found")
        return self.async_show_menu(
            step_id="mapping_action",
            menu_options=["edit_mapping", "delete_mapping"],
            description_placeholders={
                "ha_entity_id": ha_entity_id,
                "energyid_key": data[CONF_ENERGYID_KEY],
            },
        )

    async def async_step_edit_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle editing the EnergyID key for a mapping."""
        errors: dict[str, str] = {}
        if not (ha_entity_id := self._current_ha_entity_id):
            return self.async_abort(reason="no_mapping_selected")
        if not (current_data := self._get_current_mappings().get(ha_entity_id)):
            return self.async_abort(reason="mapping_not_found")

        if user_input is not None:
            new_key = user_input.get(CONF_ENERGYID_KEY, "").strip()
            errors = _validate_mapping_input(ha_entity_id, new_key, {}, is_editing=True)
            if not errors:
                new_options = dict(self.config_entry.options)
                new_options[ha_entity_id][CONF_ENERGYID_KEY] = new_key
                title = f"{ha_entity_id.split('.', 1)[-1]} → {new_key}"
                return self.async_create_entry(title=title, data=new_options)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENERGYID_KEY, default=current_data.get(CONF_ENERGYID_KEY)
                ): TextSelector()
            }
        )
        return self.async_show_form(
            step_id="edit_mapping",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "ha_entity_id": ha_entity_id,
                "current_key": current_data[CONF_ENERGYID_KEY],
            },
        )

    async def async_step_delete_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm and handle deletion of a mapping."""
        if not (ha_entity_id := self._current_ha_entity_id):
            return self.async_abort(reason="no_mapping_selected")

        if user_input is not None:
            new_options = dict(self.config_entry.options)
            if ha_entity_id in new_options:
                del new_options[ha_entity_id]
            return self.async_create_entry(title="", data=new_options)

        if not (data := self._get_current_mappings().get(ha_entity_id)):
            return self.async_abort(reason="mapping_not_found")
        return self.async_show_form(
            step_id="delete_mapping",
            data_schema=vol.Schema({}),
            description_placeholders={
                "ha_entity_id": ha_entity_id,
                "energyid_key": data[CONF_ENERGYID_KEY],
            },
        )
