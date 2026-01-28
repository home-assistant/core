"""Sensor entity for Electrolux Integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.feature_constants import (
    APPLIANCE_STATE,
    DISPLAY_FOOD_PROBE_TEMPERATURE_C,
    DISPLAY_FOOD_PROBE_TEMPERATURE_F,
    DISPLAY_TEMPERATURE_C,
    DISPLAY_TEMPERATURE_F,
    DOOR_STATE,
    FOOD_PROBE_STATE,
    REMOTE_CONTROL,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)

ELECTROLUX_TO_HA_TEMPERATURE_UNIT = {
    "CELSIUS": UnitOfTemperature.CELSIUS,
    "FAHRENHEIT": UnitOfTemperature.FAHRENHEIT,
}


@dataclass(frozen=True, kw_only=True)
class ElectroluxSensorDescription(SensorEntityDescription):
    """Custom sensor description for Electrolux sensors."""

    value_fn: Callable[..., StateType]
    is_supported_fn: Callable[..., Any] = lambda *args: None


OVEN_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="appliance_state",
        translation_key="appliance_state",
        icon="mdi:information-outline",
        value_fn=lambda appliance: appliance.get_current_appliance_state(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            APPLIANCE_STATE
        ),
    ),
    ElectroluxSensorDescription(
        key="food_probe_state",
        translation_key="food_probe_state",
        icon="mdi:thermometer-probe",
        value_fn=lambda appliance: appliance.get_current_food_probe_insertion_state(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            FOOD_PROBE_STATE
        ),
    ),
    ElectroluxSensorDescription(
        key="door_state",
        translation_key="door_state",
        icon="mdi:door",
        value_fn=lambda appliance: appliance.get_current_door_state(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(DOOR_STATE),
    ),
    ElectroluxSensorDescription(
        key="remote_control",
        translation_key="remote_control",
        icon="mdi:remote",
        value_fn=lambda appliance: appliance.get_current_remote_control().lower(),
        device_class=SensorDeviceClass.ENUM,
        options=["enabled", "disabled", "not_safety_relevant_enabled"],
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            REMOTE_CONTROL
        ),
    ),
)

OVEN_TEMPERATURE_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="food_probe_temperature",
        translation_key="food_probe_temperature",
        icon="mdi:thermometer-probe",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class="measurement",
        value_fn=lambda appliance,
        temp_unit=None: appliance.get_current_display_food_probe_temperature_f()
        if temp_unit == UnitOfTemperature.FAHRENHEIT
        else appliance.get_current_display_food_probe_temperature_c(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_FOOD_PROBE_TEMPERATURE_F, DISPLAY_FOOD_PROBE_TEMPERATURE_C]
        ),
    ),
    ElectroluxSensorDescription(
        key="display_temperature",
        translation_key="display_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class="measurement",
        value_fn=lambda appliance,
        temp_unit=None: appliance.get_current_display_temperature_f()
        if temp_unit == UnitOfTemperature.FAHRENHEIT
        else appliance.get_current_display_temperature_c(),
        is_supported_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_TEMPERATURE_C, DISPLAY_TEMPERATURE_F]
        ),
    ),
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return all entities for a single appliance."""
    appliance = appliance_data.appliance
    coordinator = coordinators[appliance.applianceId]
    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, OVAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, description)
            for description in OVEN_ELECTROLUX_SENSORS
            if description.is_supported_fn(appliance_data)
        )

        entities.extend(
            ElectroluxTemperatureSensor(appliance_data, coordinator, description)
            for description in OVEN_TEMPERATURE_ELECTROLUX_SENSORS
            if description.is_supported_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set sensor for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxSensor(ElectroluxBaseEntity[ApplianceData], SensorEntity):
    """Representation of a generic sensor for Electrolux appliances."""

    entity_description: ElectroluxSensorDescription

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{description.key}"
        )
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        self._attr_native_value = self._get_value()

    def _get_value(self) -> StateType:
        return self.entity_description.value_fn(self._appliance_data)


class ElectroluxTemperatureSensor(ElectroluxSensor):
    """Representation of a temperature sensor for Electrolux appliances."""

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self._appliance = cast(OVAppliance | CRAppliance, appliance_data)
        self._attr_native_unit_of_measurement = self._get_temperature_unit()
        super().__init__(appliance_data, coordinator, description)
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        self._attr_native_value = self._get_value()
        self._attr_suggested_unit_of_measurement = self._get_temperature_unit()

    def _get_value(self) -> StateType:
        return self.entity_description.value_fn(
            self._appliance_data, temp_unit=self._attr_native_unit_of_measurement
        )

    def _get_temperature_unit(self) -> UnitOfTemperature:
        temp_unit = self._appliance.get_current_temperature_unit()

        if temp_unit is not None:
            temp_unit = temp_unit.upper()

        return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(
            temp_unit, UnitOfTemperature.CELSIUS
        )
