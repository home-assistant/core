"""Number entity for Electrolux Integration."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, TypeVar, override

from electrolux_group_developer_sdk.appliance_config.cr_config import FREEZER, FRIDGE
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.feature_constants import (
    LIGHT_COLOR_TEMPERATURE,
    LIGHT_INTENSITY,
    TARGET_TEMPERATURE_C,
    TARGET_TEMPERATURE_F,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import (
    TemperatureConverter,
    TemperatureDeltaConverter,
)

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .util import (
    convert_between_units_none_safe,
    convert_to_snake_case,
    round_to_valid_step,
)

_LOGGER = logging.getLogger(__name__)

ELECTROLUX_TO_HA_TEMPERATURE_UNIT = {
    "CELSIUS": UnitOfTemperature.CELSIUS,
    "FAHRENHEIT": UnitOfTemperature.FAHRENHEIT,
}

T = TypeVar("T", bound=ApplianceData, default=ApplianceData)


@dataclass(frozen=True, kw_only=True)
class ElectroluxNumberDescription[T = ApplianceData](NumberEntityDescription):
    """Custom number description for Electrolux numbers."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T], float | None] = lambda appliance: None
    min_fn: Callable[[T], float]
    max_fn: Callable[[T], float]
    step_fn: Callable[[T], float]
    command_payload_fn: Callable[[T, float], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class ElectroluxTemperatureNumberDescription[T = ApplianceData](
    NumberEntityDescription
):
    """Custom number description for Electrolux temperature numbers."""

    exists_fn: Callable[[T], bool] = lambda appliance: True
    value_fn: Callable[[T, UnitOfTemperature], float | None] = (
        lambda appliance, temp_unit: None
    )
    min_fn: Callable[[T], float]
    max_fn: Callable[[T], float]
    step_fn: Callable[[T], float]
    command_payload_fn: Callable[[T, UnitOfTemperature, float], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class ElectroluxSubmoduleTemperatureNumberDescription[T = ApplianceData](
    NumberEntityDescription
):
    """Custom number description for Electrolux temperature numbers."""

    exists_fn: Callable[[T, str], bool] = lambda appliance, submodule: True
    value_fn: Callable[[T, str, UnitOfTemperature], float | None] = (
        lambda appliance, submodule, temp_unit: None
    )
    min_fn: Callable[[T, str], float]
    max_fn: Callable[[T, str], float]
    step_fn: Callable[[T, str], float]
    command_payload_fn: Callable[[T, str, UnitOfTemperature, float], dict[str, Any]]


OVEN_TEMPERATURE_NUMBERS: tuple[
    ElectroluxTemperatureNumberDescription[OVAppliance], ...
] = (
    ElectroluxTemperatureNumberDescription(
        key="target_temperature",
        translation_key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        exists_fn=lambda appliance: appliance.is_feature_supported(
            [TARGET_TEMPERATURE_C, TARGET_TEMPERATURE_F]
        ),
        value_fn=lambda appliance, temp_unit: (
            appliance.get_current_target_temperature_c()
            if temp_unit == UnitOfTemperature.CELSIUS
            else appliance.get_current_target_temperature_f()
        ),
        min_fn=lambda appliance: appliance.get_supported_min_temp(),
        max_fn=lambda appliance: appliance.get_supported_max_temp(),
        step_fn=lambda appliance: appliance.get_supported_step_temp(),
        command_payload_fn=lambda appliance, temp_unit, value: (
            appliance.get_temperature_c_command(value)
            if temp_unit == UnitOfTemperature.CELSIUS
            else appliance.get_temperature_f_command(value)
        ),
    ),
)

STRUCTURED_OVEN_TEMPERATURE_NUMBERS: tuple[
    ElectroluxSubmoduleTemperatureNumberDescription[SOAppliance], ...
] = (
    ElectroluxSubmoduleTemperatureNumberDescription(
        key="target_temperature",
        translation_key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        exists_fn=lambda appliance, submodule: appliance.is_cavity_feature_supported(
            submodule, [TARGET_TEMPERATURE_C, TARGET_TEMPERATURE_F]
        ),
        value_fn=lambda appliance, submodule, temp_unit: (
            appliance.get_current_cavity_target_temperature_c(submodule)
            if temp_unit == UnitOfTemperature.CELSIUS
            else appliance.get_current_cavity_target_temperature_f(submodule)
        ),
        min_fn=lambda appliance, submodule: appliance.get_cavity_supported_min_temp(
            submodule
        ),
        max_fn=lambda appliance, submodule: appliance.get_cavity_supported_max_temp(
            submodule
        ),
        step_fn=lambda appliance, submodule: appliance.get_cavity_supported_step_temp(
            submodule
        ),
        command_payload_fn=lambda appliance, submodule, temp_unit, value: (
            appliance.get_temperature_c_command(submodule, value)
            if temp_unit == UnitOfTemperature.CELSIUS
            else appliance.get_temperature_f_command(submodule, value)
        ),
    ),
)

FRIDGE_FREEZER_TEMPERATURE_NUMBERS: tuple[
    ElectroluxSubmoduleTemperatureNumberDescription[CRAppliance], ...
] = (
    ElectroluxSubmoduleTemperatureNumberDescription[CRAppliance](
        key="target_temperature",
        translation_key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        exists_fn=lambda appliance, submodule: (
            appliance.is_cavity_feature_supported(submodule, TARGET_TEMPERATURE_C)
            or appliance.is_cavity_feature_supported(submodule, TARGET_TEMPERATURE_F)
        ),
        value_fn=lambda appliance, submodule, temp_unit: (
            appliance.get_current_cavity_target_temperature_c(submodule)
            if temp_unit == UnitOfTemperature.CELSIUS
            else appliance.get_current_cavity_target_temperature_f(submodule)
        ),
        min_fn=lambda appliance, submodule: appliance.get_supported_min_temperature(
            submodule
        ),
        max_fn=lambda appliance, submodule: appliance.get_supported_max_temperature(
            submodule
        ),
        step_fn=lambda appliance, submodule: appliance.get_supported_step_temperature(
            submodule
        ),
        command_payload_fn=lambda appliance, submodule, temp_unit, value: (
            appliance.get_set_cavity_temperature_c_command(submodule, value)
            if temp_unit == UnitOfTemperature.CELSIUS
            else appliance.get_set_cavity_temperature_f_command(submodule, value)
        ),
    ),
)

HOOD_NUMBERS: tuple[ElectroluxNumberDescription[HDAppliance], ...] = (
    ElectroluxNumberDescription(
        key="light_color",
        translation_key="light_color",
        exists_fn=lambda appliance: appliance.is_feature_supported(
            LIGHT_COLOR_TEMPERATURE
        ),
        value_fn=lambda appliance: appliance.get_current_light_color_temperature(),
        min_fn=lambda appliance: appliance.get_min_light_color_temperature_range(),
        max_fn=lambda appliance: appliance.get_max_light_color_temperature_range(),
        step_fn=lambda appliance: appliance.get_step_light_color_temperature_range(),
        command_payload_fn=lambda appliance, value: (
            appliance.get_set_light_color_temperature_command(round(value))
        ),
    ),
    ElectroluxNumberDescription(
        key="light_intensity",
        translation_key="light_intensity",
        exists_fn=lambda appliance: appliance.is_feature_supported(LIGHT_INTENSITY),
        value_fn=lambda appliance: appliance.get_current_light_intensity(),
        min_fn=lambda appliance: appliance.get_min_light_intensity(),
        max_fn=lambda appliance: appliance.get_max_light_intensity(),
        step_fn=lambda appliance: appliance.get_step_light_intensity(),
        command_payload_fn=lambda appliance, value: (
            appliance.get_set_light_intensity_command(round(value))
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
            ElectroluxTemperatureNumber(appliance_data, coordinator, description)
            for description in OVEN_TEMPERATURE_NUMBERS
            if description.exists_fn(appliance_data)
        )

    if isinstance(appliance_data, SOAppliance):
        entities.extend(
            ElectroluxSubmoduleTemperatureNumber(
                appliance_data, coordinator, description, cavity
            )
            for cavity in appliance_data.get_supported_cavities()
            for description in STRUCTURED_OVEN_TEMPERATURE_NUMBERS
            if description.exists_fn(appliance_data, cavity)
        )

    if isinstance(appliance_data, CRAppliance):
        target_temperature_cavities = [FRIDGE, FREEZER]
        cavities = [
            cavity
            for cavity in appliance_data.get_supported_cavities()
            if cavity in target_temperature_cavities
        ]

        entities.extend(
            ElectroluxSubmoduleTemperatureNumber(
                appliance_data, coordinator, description, cavity
            )
            for cavity in cavities
            for description in FRIDGE_FREEZER_TEMPERATURE_NUMBERS
            if description.exists_fn(appliance_data, cavity)
        )

    if isinstance(appliance_data, HDAppliance):
        entities.extend(
            ElectroluxNumber(appliance_data, coordinator, description)
            for description in HOOD_NUMBERS
            if description.exists_fn(appliance_data)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Number entity for Electrolux Integration."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBaseNumber(ElectroluxBaseEntity[T], NumberEntity, ABC):
    """Base class for Electrolux integration number entities."""

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the number box."""
        super().__init__(appliance_data, coordinator, unique_id_suffix)
        # setting default values for min, max and step so the attributes are created by the time _update_attr_state is called
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0

    @override
    def _update_attr_state(self) -> bool:
        state_updated = False

        new_value = self._get_value()
        if self._attr_native_value != new_value:
            self._attr_native_value = new_value
            state_updated = True

        new_min = self._get_min()
        if self._attr_native_min_value != new_min:
            self._attr_native_min_value = new_min
            state_updated = True

        new_max = self._get_max()
        if self._attr_native_max_value != new_max:
            self._attr_native_max_value = new_max
            state_updated = True

        new_step = self._get_step()
        if self._attr_native_step != new_step:
            self._attr_native_step = new_step
            state_updated = True

        return state_updated

    @abstractmethod
    def _get_value(self) -> float | None:
        raise NotImplementedError

    @abstractmethod
    def _get_min(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def _get_max(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def _get_step(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def _get_command_payload(self, value: float) -> dict[str, Any]:
        raise NotImplementedError

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set Electrolux number to value."""
        command = self._get_command_payload(value)
        await self.coordinator.client.send_command(self._appliance_id, command)


class ElectroluxNumber(ElectroluxBaseNumber[T]):
    """Representation of an Electrolux light intensity selection."""

    entity_description: ElectroluxNumberDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxNumberDescription[T],
    ) -> None:
        """Initialize the number box."""
        super().__init__(appliance_data, coordinator, description.key)
        self.entity_description = description

    @override
    def _get_value(self) -> float | None:
        return self.entity_description.value_fn(self._appliance_data)

    @override
    def _get_min(self) -> float:
        return self.entity_description.min_fn(self._appliance_data)

    @override
    def _get_max(self) -> float:
        return self.entity_description.max_fn(self._appliance_data)

    @override
    def _get_step(self) -> float:
        return self.entity_description.step_fn(self._appliance_data)

    @override
    def _get_command_payload(self, value: float) -> dict[str, Any]:
        rounded_value = round_to_valid_step(value, self._get_min(), self._get_step())
        return self.entity_description.command_payload_fn(
            self._appliance_data, rounded_value
        )


class ElectroluxTemperatureNumber[T: OVAppliance](ElectroluxBaseNumber[T]):
    """Representation of an Electrolux light intensity selection."""

    entity_description: ElectroluxTemperatureNumberDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxTemperatureNumberDescription[T],
    ) -> None:
        """Initialize the number box."""
        super().__init__(appliance_data, coordinator, description.key)
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self.entity_description = description

    @override
    def _get_min(self) -> float:
        temp_unit = self._get_temperature_unit()
        minimum = self.entity_description.min_fn(self._appliance_data)
        return TemperatureConverter.convert(
            minimum, temp_unit, UnitOfTemperature.CELSIUS
        )

    @override
    def _get_max(self) -> float:
        temp_unit = self._get_temperature_unit()
        maximum = self.entity_description.max_fn(self._appliance_data)
        return TemperatureConverter.convert(
            maximum, temp_unit, UnitOfTemperature.CELSIUS
        )

    @override
    def _get_step(self) -> float:
        temp_unit = self._get_temperature_unit()
        step = self.entity_description.step_fn(self._appliance_data)
        return TemperatureDeltaConverter.convert(
            step, temp_unit, UnitOfTemperature.CELSIUS
        )

    @override
    def _get_command_payload(self, value: float) -> dict[str, Any]:
        temp_unit = self._get_temperature_unit()
        converted_value = TemperatureConverter.convert(
            value, UnitOfTemperature.CELSIUS, temp_unit
        )
        rounded_value = round_to_valid_step(
            converted_value,
            self.entity_description.min_fn(self._appliance_data),
            self.entity_description.step_fn(self._appliance_data),
        )
        return self.entity_description.command_payload_fn(
            self._appliance_data, temp_unit, rounded_value
        )

    @override
    def _get_value(self) -> float | None:
        temp_unit = self._get_temperature_unit()
        temp_value = self.entity_description.value_fn(self._appliance_data, temp_unit)
        return convert_between_units_none_safe(
            temp_value, temp_unit, UnitOfTemperature.CELSIUS
        )

    def _get_temperature_unit(self) -> UnitOfTemperature:
        temp_unit = self._appliance_data.get_current_temperature_unit()

        if temp_unit is not None:
            temp_unit = temp_unit.upper()

        return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(
            temp_unit, UnitOfTemperature.CELSIUS
        )


class ElectroluxSubmoduleTemperatureNumber[T: CRAppliance | SOAppliance](
    ElectroluxBaseNumber[T]
):
    """Representation of an Electrolux light intensity selection."""

    entity_description: ElectroluxSubmoduleTemperatureNumberDescription[T]

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSubmoduleTemperatureNumberDescription[T],
        submodule: str,
    ) -> None:
        """Initialize the number box."""
        entity_key = f"{convert_to_snake_case(submodule)}_{description.key}"
        super().__init__(appliance_data, coordinator, entity_key)
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self.entity_description = description
        self._submodule = submodule
        self._attr_translation_key = (
            f"{convert_to_snake_case(submodule)}_{description.translation_key}"
        )

    @override
    def _get_min(self) -> float:
        temp_unit = self._get_temperature_unit()
        minimum = self.entity_description.min_fn(self._appliance_data, self._submodule)
        return TemperatureConverter.convert(
            minimum, temp_unit, UnitOfTemperature.CELSIUS
        )

    @override
    def _get_max(self) -> float:
        temp_unit = self._get_temperature_unit()
        maximum = self.entity_description.max_fn(self._appliance_data, self._submodule)
        return TemperatureConverter.convert(
            maximum, temp_unit, UnitOfTemperature.CELSIUS
        )

    @override
    def _get_step(self) -> float:
        temp_unit = self._get_temperature_unit()
        step = self.entity_description.step_fn(self._appliance_data, self._submodule)
        return TemperatureDeltaConverter.convert(
            step, temp_unit, UnitOfTemperature.CELSIUS
        )

    @override
    def _get_command_payload(self, value: float) -> dict[str, Any]:
        temp_unit = self._get_temperature_unit()
        converted_value = TemperatureConverter.convert(
            value, UnitOfTemperature.CELSIUS, temp_unit
        )
        rounded_value = round_to_valid_step(
            converted_value,
            self.entity_description.min_fn(self._appliance_data, self._submodule),
            self.entity_description.step_fn(self._appliance_data, self._submodule),
        )
        return self.entity_description.command_payload_fn(
            self._appliance_data, self._submodule, temp_unit, rounded_value
        )

    @override
    def _get_value(self) -> float | None:
        temp_unit = self._get_temperature_unit()
        temp_value = self.entity_description.value_fn(
            self._appliance_data, self._submodule, temp_unit
        )
        return convert_between_units_none_safe(
            temp_value, temp_unit, UnitOfTemperature.CELSIUS
        )

    def _get_temperature_unit(self) -> UnitOfTemperature:
        temp_unit = self._appliance_data.get_current_temperature_unit()

        if temp_unit is not None:
            temp_unit = temp_unit.upper()

        return ELECTROLUX_TO_HA_TEMPERATURE_UNIT.get(
            temp_unit, UnitOfTemperature.CELSIUS
        )
