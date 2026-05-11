"""Sensor entity for Electrolux Integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

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
    FOOD_PROBE_STATE,
    REMOTE_CONTROL,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

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
    exists_fn: Callable[[ApplianceData], bool] = lambda *args: True
    feature_name: str | None = None
    known_values: set[str] | None = None


OVEN_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="appliance_state",
        translation_key="appliance_state",
        icon="mdi:information-outline",
        value_fn=lambda appliance: appliance.get_current_appliance_state(),
        device_class=SensorDeviceClass.ENUM,
        feature_name=APPLIANCE_STATE,
        exists_fn=lambda appliance: appliance.is_feature_supported(APPLIANCE_STATE),
        known_values={
            "alarm",
            "delayed_start",
            "end_of_cycle",
            "idle",
            "off",
            "paused",
            "ready_to_start",
            "running",
        },
    ),
    ElectroluxSensorDescription(
        key="food_probe_state",
        translation_key="food_probe_state",
        icon="mdi:thermometer-probe",
        value_fn=lambda appliance: appliance.get_current_food_probe_insertion_state(),
        device_class=SensorDeviceClass.ENUM,
        feature_name=FOOD_PROBE_STATE,
        exists_fn=lambda appliance: appliance.is_feature_supported(FOOD_PROBE_STATE),
        known_values={
            "inserted",
            "not_inserted",
        },
    ),
    ElectroluxSensorDescription(
        key="remote_control",
        translation_key="remote_control",
        icon="mdi:remote",
        value_fn=lambda appliance: appliance.get_current_remote_control(),
        device_class=SensorDeviceClass.ENUM,
        feature_name=REMOTE_CONTROL,
        exists_fn=lambda appliance: appliance.is_feature_supported(REMOTE_CONTROL),
        known_values={
            "disabled",
            "enabled",
            "not_safety_relevant_enabled",
            "temporary_locked",
        },
    ),
)

OVEN_TEMPERATURE_ELECTROLUX_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="food_probe_temperature",
        translation_key="food_probe_temperature",
        icon="mdi:thermometer-probe",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda appliance, temp_unit=None: (
            appliance.get_current_display_food_probe_temperature_f()
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_display_food_probe_temperature_c()
        ),
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [DISPLAY_FOOD_PROBE_TEMPERATURE_F, DISPLAY_FOOD_PROBE_TEMPERATURE_C]
        ),
    ),
    ElectroluxSensorDescription(
        key="display_temperature",
        translation_key="display_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda appliance, temp_unit=None: (
            appliance.get_current_display_temperature_f()
            if temp_unit == UnitOfTemperature.FAHRENHEIT
            else appliance.get_current_display_temperature_c()
        ),
        exists_fn=lambda appliance: appliance.is_feature_supported(
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
            if description.exists_fn(appliance_data)
        )

        entities.extend(
            ElectroluxTemperatureSensor(appliance_data, coordinator, description)
            for description in OVEN_TEMPERATURE_ELECTROLUX_SENSORS
            if description.exists_fn(appliance_data)
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
        super().__init__(appliance_data, coordinator, description.key)

        if (
            description.feature_name is not None
            and description.known_values is not None
        ):
            options = appliance_data.get_feature_state_string_options(
                description.feature_name
            )
            snake_case_options = [
                snake_case_option
                for option in options
                if (snake_case_option := _convert_to_snake_case(option))
                in description.known_values
            ]

            if len(snake_case_options) > 0:
                self._attr_options = snake_case_options

        self.entity_description = description

    def _update_attr_state(self) -> bool:
        new_value = self._get_value()
        if isinstance(new_value, str):
            new_value = _convert_to_snake_case(new_value)

            if self.entity_description.known_values:
                new_value = _map_to_known_value(
                    self.entity_description.known_values,
                    self.entity_description.key,
                    new_value,
                )

        if self._attr_native_value != new_value:
            self._attr_native_value = new_value
            return True

        return False

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
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        super().__init__(appliance_data, coordinator, description)

    def _get_value(self) -> StateType:
        temp_unit = self._get_temperature_unit()
        temp_value: float | None = cast(
            float | None,
            self.entity_description.value_fn(self._appliance_data, temp_unit=temp_unit),
        )
        if temp_value is None:
            return None
        return TemperatureConverter.convert(
            temp_value, temp_unit, UnitOfTemperature.CELSIUS
        )

    def _get_temperature_unit(self) -> UnitOfTemperature:
        temp_unit = self._appliance.get_current_temperature_unit()

        if temp_unit is not None:
            temp_unit = temp_unit.upper()

        return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(
            temp_unit, UnitOfTemperature.CELSIUS
        )


def _convert_to_snake_case(x: str) -> str:
    """Converts a string to snake case."""
    lower_case = x.lower()
    return "".join([_convert_char_to_snake_case(char) for char in lower_case])


def _convert_char_to_snake_case(char: str) -> str:
    if char.isspace():
        return "_"
    return char


def _map_to_known_value(
    known_values: set[str], entity_key: str, value: str
) -> str | None:
    """Return provided value if it is known, otherwise log warn message and return None."""
    if value not in known_values:
        _LOGGER.warning(
            "An unknown value %s was reported for a sensor of the Electrolux integration. "
            "Please report it for the integration, and include the following information: "
            'entity key="%s", reported value="%s"',
            value,
            entity_key,
            value,
        )
        return None
    return value
