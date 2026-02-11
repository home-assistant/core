"""Support for number entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN, UNIT_MAP
from .entity import SmartThingsEntity, SmartThingsFsvEntity


class FsvSettingProperty(StrEnum):
    """FSV setting property keys."""

    ID = "id"
    TYPE = "type"
    TEMPERATURE_UNIT = "temperatureUnit"
    MIN_VALUE = "minValue"
    MAX_VALUE = "maxValue"
    RESOLUTION = "resolution"
    VALUE = "value"


class FsvSettingType(StrEnum):
    """FSV setting types."""

    TEMPERATURE = "temperature"


@dataclass(frozen=True, kw_only=True)
class SmartThingsFsvEntityDescription(NumberEntityDescription):
    """Describe a SmartThings FSV setting number entity."""

    fsv_id: str
    is_temperature_type: bool = False


# Mapping of FSV setting IDs to entity descriptions
# Binary (0/1) settings and enum-like settings are excluded as they should be
# switches or selects respectively
FSV_NUMBER_DESCRIPTIONS: dict[str, SmartThingsFsvEntityDescription] = {
    "1021": SmartThingsFsvEntityDescription(
        key="1021",
        fsv_id="1021",
        translation_key="target_room_temperature_upper_limit",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "1022": SmartThingsFsvEntityDescription(
        key="1022",
        fsv_id="1022",
        translation_key="target_room_temperature_lower_limit",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "1031": SmartThingsFsvEntityDescription(
        key="1031",
        fsv_id="1031",
        translation_key="target_water_outlet_upper_limit_heating",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "1032": SmartThingsFsvEntityDescription(
        key="1032",
        fsv_id="1032",
        translation_key="target_water_outlet_lower_limit_heating",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "1051": SmartThingsFsvEntityDescription(
        key="1051",
        fsv_id="1051",
        translation_key="maximum_dhw_tank_temperature_user_limit",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "1052": SmartThingsFsvEntityDescription(
        key="1052",
        fsv_id="1052",
        translation_key="target_dhw_tank_temperature_lower_limit_user_limit",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2011": SmartThingsFsvEntityDescription(
        key="2011",
        fsv_id="2011",
        translation_key="water_law_low_ambient_outdoor_temp_setpoint",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2012": SmartThingsFsvEntityDescription(
        key="2012",
        fsv_id="2012",
        translation_key="water_law_high_ambient_outdoor_temp_setpoint",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2021": SmartThingsFsvEntityDescription(
        key="2021",
        fsv_id="2021",
        translation_key="water_law_flow_temp_at_low_ambient_zone_1",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2022": SmartThingsFsvEntityDescription(
        key="2022",
        fsv_id="2022",
        translation_key="water_law_flow_temp_at_high_ambient_zone_1",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2031": SmartThingsFsvEntityDescription(
        key="2031",
        fsv_id="2031",
        translation_key="water_law_flow_temp_at_low_ambient_zone_2",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2032": SmartThingsFsvEntityDescription(
        key="2032",
        fsv_id="2032",
        translation_key="water_law_flow_temp_at_high_ambient_zone_2",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "2093": SmartThingsFsvEntityDescription(
        key="2093",
        fsv_id="2093",
        translation_key="remote_controller_room_temp_control_internal_sensor",
        entity_category=EntityCategory.CONFIG,
    ),
    "3021": SmartThingsFsvEntityDescription(
        key="3021",
        fsv_id="3021",
        translation_key="maximum_dhw_tank_temperature_heat_pump_limit",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "3022": SmartThingsFsvEntityDescription(
        key="3022",
        fsv_id="3022",
        translation_key="dhw_hysteresis_temperature_difference_hp_off",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "3023": SmartThingsFsvEntityDescription(
        key="3023",
        fsv_id="3023",
        translation_key="dhw_hysteresis_temperature_difference_hp_on",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "3025": SmartThingsFsvEntityDescription(
        key="3025",
        fsv_id="3025",
        translation_key="max_cylinder_heating_time_hp_vs_space_heating",
        entity_category=EntityCategory.CONFIG,
    ),
    "3032": SmartThingsFsvEntityDescription(
        key="3032",
        fsv_id="3032",
        translation_key="max_cylinder_heating_time_hp_before_booster_assist",
        entity_category=EntityCategory.CONFIG,
    ),
    "3042": SmartThingsFsvEntityDescription(
        key="3042",
        fsv_id="3042",
        translation_key="anti_legionella_function_day",
        entity_category=EntityCategory.CONFIG,
    ),
    "3043": SmartThingsFsvEntityDescription(
        key="3043",
        fsv_id="3043",
        translation_key="anti_legionella_function_start_time",
        entity_category=EntityCategory.CONFIG,
    ),
    "3044": SmartThingsFsvEntityDescription(
        key="3044",
        fsv_id="3044",
        translation_key="anti_legionella_function_target_temperature",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "3045": SmartThingsFsvEntityDescription(
        key="3045",
        fsv_id="3045",
        translation_key="anti_legionella_function_hold_time",
        entity_category=EntityCategory.CONFIG,
    ),
    "3052": SmartThingsFsvEntityDescription(
        key="3052",
        fsv_id="3052",
        translation_key="hotwater_boost_timer_duration",
        entity_category=EntityCategory.CONFIG,
    ),
    "3081": SmartThingsFsvEntityDescription(
        key="3081",
        fsv_id="3081",
        translation_key="back_up_heater_1st_step",
        entity_category=EntityCategory.CONFIG,
    ),
    "3082": SmartThingsFsvEntityDescription(
        key="3082",
        fsv_id="3082",
        translation_key="back_up_heater_2nd_step",
        entity_category=EntityCategory.CONFIG,
    ),
    "3083": SmartThingsFsvEntityDescription(
        key="3083",
        fsv_id="3083",
        translation_key="booster_heater_capacity_kw_rating",
        entity_category=EntityCategory.CONFIG,
    ),
    "4012": SmartThingsFsvEntityDescription(
        key="4012",
        fsv_id="4012",
        translation_key="outdoor_temperature_for_priority_changeover",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "4042": SmartThingsFsvEntityDescription(
        key="4042",
        fsv_id="4042",
        translation_key="mixing_valve_target_temperature_difference_heating",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "4052": SmartThingsFsvEntityDescription(
        key="4052",
        fsv_id="4052",
        translation_key="inverter_pump_control_target_deltat",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
    "4053": SmartThingsFsvEntityDescription(
        key="4053",
        fsv_id="4053",
        translation_key="inverter_pump_control_control_factor_gain",
        entity_category=EntityCategory.CONFIG,
    ),
    "4054": SmartThingsFsvEntityDescription(
        key="4054",
        fsv_id="4054",
        translation_key="inverter_pump_control_pwm_minimum_output",
        entity_category=EntityCategory.CONFIG,
    ),
    "5021": SmartThingsFsvEntityDescription(
        key="5021",
        fsv_id="5021",
        translation_key="dhw_temp_reduction_offset",
        entity_category=EntityCategory.CONFIG,
    ),
    "5083": SmartThingsFsvEntityDescription(
        key="5083",
        fsv_id="5083",
        translation_key="pv_control_heating_setpoint_addition",
        is_temperature_type=True,
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add number entities for a config entry."""
    entry_data = entry.runtime_data
    entities: list[NumberEntity] = [
        SmartThingsWasherRinseCyclesNumberEntity(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.CUSTOM_WASHER_RINSE_CYCLES in device.status[MAIN]
    ]
    entities.extend(
        SmartThingsHoodNumberEntity(entry_data.client, device)
        for device in entry_data.devices.values()
        if (
            (hood_component := device.status.get("hood")) is not None
            and Capability.SAMSUNG_CE_HOOD_FAN_SPEED in hood_component
            and Capability.SAMSUNG_CE_CONNECTION_STATE not in hood_component
        )
    )
    entities.extend(
        SmartThingsRefrigeratorTemperatureNumberEntity(
            entry_data.client, device, component
        )
        for device in entry_data.devices.values()
        for component in device.status
        if component in ("cooler", "freezer", "onedoor")
        and Capability.THERMOSTAT_COOLING_SETPOINT in device.status[component]
    )
    entities.extend(
        SmartThingsFsvSettings(
            entry_data.client, device, component, fsv_setting, description
        )
        for device in entry_data.devices.values()
        for component in device.status
        if Capability.SAMSUNG_CE_EHS_FSV_SETTINGS in device.status[component]
        for fsv_settings in device.status[component][
            Capability.SAMSUNG_CE_EHS_FSV_SETTINGS
        ].values()
        if fsv_settings.value is not None and isinstance(fsv_settings.value, list)
        for fsv_setting in fsv_settings.value
        if (fsv_id := fsv_setting[FsvSettingProperty.ID]) in FSV_NUMBER_DESCRIPTIONS
        and (description := FSV_NUMBER_DESCRIPTIONS[fsv_id])
    )
    async_add_entities(entities)


class SmartThingsWasherRinseCyclesNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_translation_key = "washer_rinse_cycles"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the instance."""
        super().__init__(client, device, {Capability.CUSTOM_WASHER_RINSE_CYCLES})
        self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{Capability.CUSTOM_WASHER_RINSE_CYCLES}_{Attribute.WASHER_RINSE_CYCLES}_{Attribute.WASHER_RINSE_CYCLES}"

    @property
    def options(self) -> list[int]:
        """Return the list of options."""
        values = self.get_attribute_value(
            Capability.CUSTOM_WASHER_RINSE_CYCLES,
            Attribute.SUPPORTED_WASHER_RINSE_CYCLES,
        )
        return [int(value) for value in values] if values else []

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.CUSTOM_WASHER_RINSE_CYCLES, Attribute.WASHER_RINSE_CYCLES
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return min(self.options)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return max(self.options)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.CUSTOM_WASHER_RINSE_CYCLES,
            Command.SET_WASHER_RINSE_CYCLES,
            str(int(value)),
        )


class SmartThingsHoodNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_translation_key = "hood_fan_speed"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the instance."""
        super().__init__(
            client, device, {Capability.SAMSUNG_CE_HOOD_FAN_SPEED}, component="hood"
        )
        self._attr_unique_id = f"{device.device.device_id}_hood_{Capability.SAMSUNG_CE_HOOD_FAN_SPEED}_{Attribute.HOOD_FAN_SPEED}_{Attribute.HOOD_FAN_SPEED}"

    @property
    def options(self) -> list[int]:
        """Return the list of options."""
        min_value = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Attribute.SETTABLE_MIN_FAN_SPEED,
        )
        max_value = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Attribute.SETTABLE_MAX_FAN_SPEED,
        )
        return list(range(min_value, max_value + 1))

    @property
    def native_value(self) -> int:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.SAMSUNG_CE_HOOD_FAN_SPEED, Attribute.HOOD_FAN_SPEED
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return min(self.options)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return max(self.options)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Command.SET_HOOD_FAN_SPEED,
            int(value),
        )


class SmartThingsRefrigeratorTemperatureNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.TEMPERATURE

    def __init__(self, client: SmartThings, device: FullDevice, component: str) -> None:
        """Initialize the instance."""
        super().__init__(
            client,
            device,
            {Capability.THERMOSTAT_COOLING_SETPOINT},
            component=component,
        )
        self._attr_unique_id = f"{device.device.device_id}_{component}_{Capability.THERMOSTAT_COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}"
        unit = self._internal_state[Capability.THERMOSTAT_COOLING_SETPOINT][
            Attribute.COOLING_SETPOINT
        ].unit
        assert unit is not None
        self._attr_native_unit_of_measurement = UNIT_MAP[unit]
        self._attr_translation_key = {
            "cooler": "cooler_temperature",
            "freezer": "freezer_temperature",
            "onedoor": "target_temperature",
        }.get(component)

    @property
    def range(self) -> dict[str, int]:
        """Return the list of options."""
        return self.get_attribute_value(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Attribute.COOLING_SETPOINT_RANGE,
        )

    @property
    def native_value(self) -> int:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.THERMOSTAT_COOLING_SETPOINT, Attribute.COOLING_SETPOINT
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.range["minimum"]

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.range["maximum"]

    @property
    def native_step(self) -> float:
        """Return the step value."""
        return self.range["step"]

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            int(value),
        )


class SmartThingsFsvSettings(SmartThingsFsvEntity, NumberEntity):
    """Define a SmartThings FSV setting number."""

    entity_description: SmartThingsFsvEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        component: str,
        fsv_setting: dict,
        description: SmartThingsFsvEntityDescription,
    ) -> None:
        """Initialize the instance."""
        super().__init__(
            client,
            device,
            component=component,
            fsv_id=description.fsv_id,
        )
        self.entity_description = description

        if (
            description.is_temperature_type
            and fsv_setting[FsvSettingProperty.TYPE] == FsvSettingType.TEMPERATURE
        ):
            self._attr_native_unit_of_measurement = UNIT_MAP[
                fsv_setting[FsvSettingProperty.TEMPERATURE_UNIT]
            ]
            self._attr_device_class = NumberDeviceClass.TEMPERATURE

        self._attr_native_min_value = fsv_setting[FsvSettingProperty.MIN_VALUE]
        self._attr_native_max_value = fsv_setting[FsvSettingProperty.MAX_VALUE]
        self._attr_native_step = fsv_setting[FsvSettingProperty.RESOLUTION]

    @property
    def native_value(self) -> int | None:
        """Return the current value."""
        return self._get_fsv_value()

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self._async_set_fsv_value(int(value))
